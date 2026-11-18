// 演说家遇袭: every shape and picture of a frame, one quad each, shaded per pixel. Each carries the
// painter's transform (device to local), so shapes are measured in their own units: coverage from
// the exact distance to the edge times the pixels per unit, paint in local units, pictures sampled
// bilinear (Qt's smooth transform), all blended premultiplied in the painter's order.

struct Prim {
    kind: vec4<u32>,
    bbox: vec4<f32>,
    inv0: vec4<f32>,
    inv1: vec4<f32>,
    shape: vec4<f32>,
    grad: vec4<f32>,
    stops: vec4<f32>,
    more: vec4<f32>,
    colors: array<vec4<f32>, 4>,
};

@group(0) @binding(0) var<storage, read> prims: array<Prim>;
@group(0) @binding(1) var<storage, read> points: array<vec2<f32>>;
@group(0) @binding(2) var pic: texture_2d<f32>;
@group(0) @binding(3) var keep: texture_2d<f32>;
@group(0) @binding(4) var<uniform> size: vec4<f32>;

struct Out {
    @builtin(position) pos: vec4<f32>,
    @location(0) @interpolate(flat) index: u32,
};

@vertex
fn vs(@builtin(vertex_index) v: u32, @builtin(instance_index) i: u32) -> Out {
    let b = prims[i].bbox;
    let corner = array<vec2<f32>, 6>(vec2(0.0, 0.0), vec2(1.0, 0.0), vec2(0.0, 1.0), vec2(1.0, 0.0), vec2(1.0, 1.0), vec2(0.0, 1.0))[v];
    let p = clamp(mix(b.xy, b.zw, corner), vec2(0.0), size.xy);
    var out: Out;
    out.pos = vec4(p.x / size.x * 2.0 - 1.0, 1.0 - p.y / size.y * 2.0, 0.0, 1.0);
    out.index = i;
    return out;
}

fn seg_dist(p: vec2<f32>, a: vec2<f32>, b: vec2<f32>) -> f32 {
    let ab = b - a;
    let k = clamp(dot(p - a, ab) / max(dot(ab, ab), 1e-9), 0.0, 1.0);
    return distance(p, a + ab * k);
}

// Contours separated by a break point (x > 1e29), each closed; even-odd inside one contour, the
// contours laid over each other.
fn path(p: vec2<f32>, offset: u32, count: u32) -> f32 {
    var total = 0.0;
    var start = offset;
    var d = 1e9;
    var inside = false;
    for (var i = offset; i < offset + count; i++) {
        let a = points[i];
        if a.x > 1e29 {
            let c = select(clamp(0.5 - d, 0.0, 1.0), clamp(0.5 + d, 0.0, 1.0), inside);
            total = c + total * (1.0 - c);
            start = i + 1u;
            d = 1e9;
            inside = false;
            continue;
        }
        var b = points[i + 1u];
        if b.x > 1e29 {
            b = points[start];
        }
        d = min(d, seg_dist(p, a, b));
        if (a.y > p.y) != (b.y > p.y) && p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x {
            inside = !inside;
        }
    }
    return total;
}

// Signed distance to a rounded rect (x, y, w, h), negative inside.
fn rrect_sd(p: vec2<f32>, r: vec4<f32>, radius: f32) -> f32 {
    let c = r.xy + r.zw * 0.5;
    let rad = min(radius, min(r.z, r.w) * 0.5);
    let q = abs(p - c) - r.zw * 0.5 + rad;
    return length(max(q, vec2(0.0))) + min(max(q.x, q.y), 0.0) - rad;
}

fn paint(pr: Prim, p: vec2<f32>) -> vec4<f32> {
    let kind = pr.kind.y;
    if kind == 0u {
        return pr.colors[0];
    }
    var t: f32;
    if kind == 1u {
        let d = pr.grad.zw - pr.grad.xy;
        t = dot(p - pr.grad.xy, d) / max(dot(d, d), 1e-9);
    } else {
        t = distance(p, pr.grad.xy) / max(pr.grad.z, 1e-9);
    }
    t = clamp(t, 0.0, 1.0);
    var c = pr.colors[0];
    for (var i = 1u; i < pr.kind.z; i++) {
        let a = pr.stops[i - 1u];
        if t >= a {
            let span = pr.stops[i] - a;
            c = mix(pr.colors[i - 1u], pr.colors[i], select(clamp((t - a) / span, 0.0, 1.0), 1.0, span <= 0.0));
        }
    }
    return c;
}

fn texel(at: vec2<i32>, dims: vec2<i32>, masked: bool) -> vec4<f32> {
    let c = clamp(at, vec2(0), dims - 1);
    let v = textureLoad(pic, c, 0);
    if masked {
        return v * textureLoad(keep, c, 0).a;
    }
    return v;
}

fn picture(pr: Prim, q: vec2<f32>) -> vec4<f32> {
    let dims = vec2<i32>(textureDimensions(pic));
    let uv = (q - pr.shape.xy) / pr.shape.zw * vec2<f32>(dims) - 0.5;
    let f = floor(uv);
    let w = uv - f;
    let i = vec2<i32>(f);
    let masked = pr.kind.w == 1u;
    let top = mix(texel(i, dims, masked), texel(i + vec2(1, 0), dims, masked), w.x);
    let bottom = mix(texel(i + vec2(0, 1), dims, masked), texel(i + vec2(1, 1), dims, masked), w.x);
    return mix(top, bottom, w.y) * pr.colors[0].a;
}

@fragment
fn fs(in: Out) -> @location(0) vec4<f32> {
    let pr = prims[in.index];
    let p = in.pos.xy;
    let q = vec2(pr.inv0.x * p.x + pr.inv0.z * p.y + pr.inv1.x, pr.inv0.y * p.x + pr.inv0.w * p.y + pr.inv1.y);
    let px = pr.inv1.z;
    var cover = 1.0;
    switch pr.kind.x {
        case 0u: { cover = clamp(0.5 - rrect_sd(q, pr.shape, 0.0) * px, 0.0, 1.0); }
        case 1u: { cover = clamp(pr.shape.z * px + 0.5 - distance(q, pr.shape.xy) * px, 0.0, 1.0); }
        case 2u: { cover = path(p, u32(pr.shape.x), u32(pr.shape.y)); }
        case 3u: { cover = clamp(0.5 - rrect_sd(q, pr.shape, pr.more.x) * px, 0.0, 1.0); }
        case 4u: {
            let half = pr.more.y * 0.5 * px;
            cover = clamp(half + 0.5 - abs(rrect_sd(q, pr.shape, pr.more.x)) * px, 0.0, 1.0);
        }
        case 5u: {
            cover = clamp(0.5 - rrect_sd(q, pr.more, 0.0) * px, 0.0, 1.0);
            return picture(pr, q) * cover;
        }
        default: {}
    }
    return paint(pr, q) * cover;
}
