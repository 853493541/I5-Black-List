// The aurora's half-size picture (ice.py's _aurora drawn at scale 0.5), one pixel at a time: for each
// curtain its rays (filled without antialiasing, as the Python layer is), cut by the fold mask, then
// its haze band and the glow along its hem, each laid over what is below. aurora.rs explains the data.

@group(0) @binding(0) var<storage, read> data: array<f32>;

const RAYS: u32 = 96u;
const STRIDE: u32 = 1203u;
const HEAD: u32 = 4u;

@vertex
fn vs(@builtin(vertex_index) v: u32) -> @builtin(position) vec4<f32> {
    let p = array<vec2<f32>, 3>(vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0))[v];
    return vec4(p, 0.0, 1.0);
}

fn seg_dist(p: vec2<f32>, a: vec2<f32>, b: vec2<f32>) -> f32 {
    let ab = b - a;
    let k = clamp(dot(p - a, ab) / max(dot(ab, ab), 1e-9), 0.0, 1.0);
    return distance(p, a + ab * k);
}

fn over(top: vec4<f32>, below: vec4<f32>) -> vec4<f32> {
    return top + below * (1.0 - top.a);
}

// Nine premultiplied colors spread evenly from x = 0 to the width.
fn across(at: u32, k: f32) -> vec4<f32> {
    let f = clamp(k, 0.0, 1.0) * 8.0;
    let i = min(u32(f), 7u);
    let a = vec4(data[at + i * 4u], data[at + i * 4u + 1u], data[at + i * 4u + 2u], data[at + i * 4u + 3u]);
    let b = vec4(data[at + i * 4u + 4u], data[at + i * 4u + 5u], data[at + i * 4u + 6u], data[at + i * 4u + 7u]);
    return mix(a, b, f - f32(i));
}

fn rays(base: u32, p: vec2<f32>, width: f32) -> vec4<f32> {
    let step = data[base + 2u];
    let drop = data[base + 1u];
    let i = min(u32(max(p.x / step, 0.0)), RAYS - 1u);
    let f = p.x / step - f32(i);
    let hems = base + 8u;
    let tops = hems + RAYS + 1u;
    let top = mix(data[tops + i], data[tops + i + 1u], f);
    let bottom = mix(data[hems + i], data[hems + i + 1u], f) + drop;
    if p.y < top || p.y >= bottom {
        return vec4(0.0);
    }
    let y0 = (data[tops + i] + data[tops + i + 1u]) / 2.0;
    let y1 = (data[hems + i] + data[hems + i + 1u]) / 2.0 + drop;
    let t = clamp((p.y - y0) / (y1 - y0), 0.0, 1.0);
    let ray = tops + RAYS + 1u + i * 8u;
    let c1 = vec4(data[ray], data[ray + 1u], data[ray + 2u], 1.0) * data[ray + 3u];
    let c2 = vec4(data[ray + 4u], data[ray + 5u], data[ray + 6u], 1.0) * data[ray + 7u];
    var c: vec4<f32>;
    if t < 0.62 {
        c = c1 * (t / 0.62);
    } else if t < 0.9 {
        c = mix(c1, c2, (t - 0.62) / 0.28);
    } else {
        c = c2 * (1.0 - (t - 0.9) / 0.1);
    }
    let mask = ray + RAYS * 8u - i * 8u;
    let m = clamp(p.x / width, 0.0, 1.0) * 160.0;
    let j = min(u32(m), 159u);
    return c * mix(data[mask + j], data[mask + j + 1u], m - f32(j));
}

@fragment
fn fs(@builtin(position) pos: vec4<f32>) -> @location(0) vec4<f32> {
    // The picture is drawn at scale 0.5: the scene's coordinates are twice the pixel's.
    let p = pos.xy * 2.0;
    let width = data[0];
    let count = u32(data[1]);
    var acc = vec4(0.0);
    for (var n = 0u; n < count; n++) {
        let base = HEAD + n * STRIDE;
        let step = data[base + 2u];
        if data[base] > 0.0 {
            acc = over(rays(base, p, width), acc);
        }
        let hems = base + 8u;
        let colors = base + 8u + 2u * (RAYS + 1u) + RAYS * 8u + 161u;
        // The haze: between the hem raised 40u and lowered 26u, its corners every fourth ray.
        let up = data[base + 3u];
        let down = data[base + 4u];
        let wide = step * 4.0;
        let j = min(u32(max(p.x / wide, 0.0)), 23u);
        let f = p.x / wide - f32(j);
        let hem_a = data[hems + j * 4u];
        let hem_b = data[hems + j * 4u + 4u];
        let inside = p.x >= 0.0 && p.x <= width && p.y > mix(hem_a, hem_b, f) - up && p.y < mix(hem_a, hem_b, f) + down;
        var d = 1e9;
        for (var k = max(j, 1u) - 1u; k <= min(j + 1u, 23u); k++) {
            let a = vec2(f32(k) * wide, data[hems + k * 4u]);
            let b = vec2(f32(k + 1u) * wide, data[hems + k * 4u + 4u]);
            d = min(d, seg_dist(p, a - vec2(0.0, up), b - vec2(0.0, up)));
            d = min(d, seg_dist(p, a + vec2(0.0, down), b + vec2(0.0, down)));
        }
        d = min(d, min(abs(p.x), abs(width - p.x)));
        let haze = select(clamp(0.5 - d / 2.0, 0.0, 1.0), clamp(0.5 + d / 2.0, 0.0, 1.0), inside);
        acc = over(across(colors, p.x / width) * haze, acc);
        // The glow along the hem: a 5u line with round ends.
        let i = min(u32(max(p.x / step, 0.0)), RAYS - 1u);
        var e = 1e9;
        for (var k = max(i, 1u) - 1u; k <= min(i + 1u, RAYS - 1u); k++) {
            e = min(e, seg_dist(p, vec2(f32(k) * step, data[hems + k]), vec2(f32(k + 1u) * step, data[hems + k + 1u])));
        }
        let glow = clamp(data[base + 5u] / 2.0 + 0.5 - e / 2.0, 0.0, 1.0);
        acc = over(across(colors + 36u, p.x / width) * glow, acc);
    }
    return acc;
}
