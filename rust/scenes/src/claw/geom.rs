//! QTransform as the Python scene uses it: each translate / rotate / scale applies in the local
//! coordinates of what came before (Qt's order), and a point maps as x' = m11 x + m21 y + dx.

use super::light::Pt;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Affine {
    pub m11: f64,
    pub m12: f64,
    pub m21: f64,
    pub m22: f64,
    pub dx: f64,
    pub dy: f64,
}

impl Default for Affine {
    fn default() -> Self {
        Self { m11: 1.0, m12: 0.0, m21: 0.0, m22: 1.0, dx: 0.0, dy: 0.0 }
    }
}

impl Affine {
    pub fn translate(mut self, x: f64, y: f64) -> Self {
        self.dx += self.m11 * x + self.m21 * y;
        self.dy += self.m12 * x + self.m22 * y;
        self
    }

    /// Degrees, screen y down, as QTransform::rotate.
    pub fn rotate(self, degrees: f64) -> Self {
        let (s, c) = degrees.to_radians().sin_cos();
        Self { m11: self.m11 * c + self.m21 * s, m12: self.m12 * c + self.m22 * s, m21: self.m21 * c - self.m11 * s, m22: self.m22 * c - self.m12 * s, ..self }
    }

    pub fn scale(self, sx: f64, sy: f64) -> Self {
        Self { m11: self.m11 * sx, m12: self.m12 * sx, m21: self.m21 * sy, m22: self.m22 * sy, ..self }
    }

    /// This, then `inner` in its local coordinates (QPainter::setTransform(inner, combine=True)).
    pub fn then(self, inner: Affine) -> Self {
        Self {
            m11: inner.m11 * self.m11 + inner.m12 * self.m21,
            m12: inner.m11 * self.m12 + inner.m12 * self.m22,
            m21: inner.m21 * self.m11 + inner.m22 * self.m21,
            m22: inner.m21 * self.m12 + inner.m22 * self.m22,
            dx: self.dx + inner.dx * self.m11 + inner.dy * self.m21,
            dy: self.dy + inner.dx * self.m12 + inner.dy * self.m22,
        }
    }

    pub fn map(&self, p: Pt) -> Pt {
        [self.m11 * p[0] + self.m21 * p[1] + self.dx, self.m12 * p[0] + self.m22 * p[1] + self.dy]
    }

    /// Device to local, as (a, b, c, d, e, f): local = (a X + c Y + e, b X + d Y + f).
    pub fn inverse(&self) -> [f64; 6] {
        let det = self.m11 * self.m22 - self.m12 * self.m21;
        let det = if det.abs() < 1e-12 { 1e-12 } else { det };
        [
            self.m22 / det,
            -self.m12 / det,
            -self.m21 / det,
            self.m11 / det,
            (self.m21 * self.dy - self.m22 * self.dx) / det,
            (self.m12 * self.dx - self.m11 * self.dy) / det,
        ]
    }

    /// Device pixels per local unit (the square root of the area scale).
    pub fn px(&self) -> f64 {
        (self.m11 * self.m22 - self.m12 * self.m21).abs().sqrt()
    }

    /// The device bounding box of a local rect (x, y, w, h): (x0, y0, x1, y1).
    pub fn bounds(&self, r: [f64; 4]) -> [f64; 4] {
        let corners = [[r[0], r[1]], [r[0] + r[2], r[1]], [r[0], r[1] + r[3]], [r[0] + r[2], r[1] + r[3]]].map(|p| self.map(p));
        corners.iter().fold([f64::MAX, f64::MAX, f64::MIN, f64::MIN], |b, p| [b[0].min(p[0]), b[1].min(p[1]), b[2].max(p[0]), b[3].max(p[1])])
    }
}

/// claw._crescent: one slash along +x centred on 0, pointed at both ends, thickest past its middle,
/// bowed slightly.
pub fn crescent(length: f64, thick: f64) -> Vec<Pt> {
    let bend = 0.05;
    let n = 48;
    let (mut top, mut bottom) = (Vec::new(), Vec::new());
    for i in 0..=n {
        let s = f64::from(i) / f64::from(n);
        let x = (s - 0.5) * length;
        let mid = -bend * length * 4.0 * s * (1.0 - s);
        let half = thick * 0.5 * (std::f64::consts::PI * s).sin().powf(0.9) * (0.7 + 0.3 * s);
        top.push([x, mid - half]);
        bottom.push([x, mid + half * 0.7]);
    }
    top.extend(bottom.into_iter().rev());
    top
}

#[cfg(test)]
mod tests {
    use super::Affine;

    #[test]
    fn composes_in_qt_order_and_inverts() {
        let t = Affine::default().translate(100.0, 50.0).rotate(-34.0).translate(-29.0, 106.0).scale(0.92, 1.0);
        let p = t.map([10.0, -3.0]);
        let [a, b, c, d, e, f] = t.inverse();
        let back = [a * p[0] + c * p[1] + e, b * p[0] + d * p[1] + f];
        assert!((back[0] - 10.0).abs() < 1e-9 && (back[1] + 3.0).abs() < 1e-9);
        // rotate(90) takes +x to +y (screen y down).
        let r = Affine::default().rotate(90.0).map([1.0, 0.0]);
        assert!(r[0].abs() < 1e-12 && (r[1] - 1.0).abs() < 1e-12);
        let both = Affine::default().translate(5.0, 0.0).then(Affine::default().scale(2.0, 2.0));
        assert_eq!(both.map([1.0, 1.0]), [7.0, 2.0]);
    }
}
