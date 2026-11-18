// The cyber scene's shapes, every pixel shaded here: coverage from the exact distance to the edge,
// paint premultiplied, pictures sampled smooth from the atlas, the wash or a panel's layer.

struct Prim {
    kind: vec4<u32>,
    bbox: vec4<f32>,
    s0: vec4<f32>,
    s1: vec4<f32>,
    grad: vec4<f32>,
    stops: vec4<f32>,
    colors: array<vec4<f32>, 4>,
    clip: vec4<f32>,
    xf: vec4<f32>,
    xf2: vec4<f32>,
};

@group(0) @binding(0) var<storage, read> prims: array<Prim>;
@group(0) @binding(1) var<storage, read> points: array<vec2<f32>>;
@group(0) @binding(2) var<uniform> size: vec4<f32>;
@group(0) @binding(3) var smooth_px: sampler;
@group(0) @binding(4) var lobby: texture_2d<f32>;
@group(0) @binding(5) var atlas: texture_2d<f32>;
@group(0) @binding(6) var wash: texture_2d<f32>;
@group(0) @binding(7) var layer_a: texture_2d<f32>;
@group(0) @binding(8) var layer_b: texture_2d<f32>;

struct Out {
    @builtin(position) pos: vec4<f32>,
    @location(0) @interpolate(flat) index: u32,
};

@vertex
fn vs(@builtin(vertex_index) v: u32, @builtin(instance_index) i: u32) -> Out {
    let b = prims[i].bbox;
    let corner = array<vec2<f32>, 6>(vec2(0.0, 0.0), vec2(1.0, 0.0), vec2(0.0, 1.0), vec2(1.0, 0.0), vec2(1.0, 1.0), vec2(0.0, 1.0))[v];
    let p = mix(b.xy, b.zw, corner);
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

fn polygon(p: vec2<f32>, offset: u32, count: u32) -> f32 {
    var d = 1e9;
    var winding = 0;
    for (var i = 0u; i < count; i++) {
        let a = points[offset + i];
        let b = points[offset + (i + 1u) % count];
        d = min(d, seg_dist(p, a, b));
        let side = (b.x - a.x) * (p.y - a.y) - (p.x - a.x) * (b.y - a.y);
        if a.y <= p.y && b.y > p.y && side > 0.0 {
            winding += 1;
        } else if a.y > p.y && b.y <= p.y && side < 0.0 {
            winding -= 1;
        }
    }
    return select(clamp(0.5 - d, 0.0, 1.0), clamp(0.5 + d, 0.0, 1.0), winding != 0);
}

// A polyline's distance; with flat ends, nothing past its first and last points.
fn stroke(p: vec2<f32>, offset: u32, count: u32, half: f32, flat: bool) -> f32 {
    var d = 1e9;
    for (var i = 0u; i + 1u < count; i++) {
        let a = points[offset + i];
        let b = points[offset + i + 1u];
        let ab = b - a;
        let k = dot(p - a, ab) / max(dot(ab, ab), 1e-9);
        if flat && ((i == 0u && k < 0.0) || (i + 2u == count && k > 1.0)) {
            // Past a flat end: only the distance across counts, faded over the half pixel beyond.
            let across = abs(ab.x * (p.y - a.y) - ab.y * (p.x - a.x)) / max(length(ab), 1e-9);
            let past = select(k - 1.0, -k, k < 0.0) * length(ab);
            d = min(d, max(across, half + past));
            continue;
        }
        d = min(d, distance(p, a + ab * clamp(k, 0.0, 1.0)));
    }
    if half < 0.5 {
        return clamp(1.0 - d, 0.0, 1.0) * half * 2.0;
    }
    return clamp(half + 0.5 - d, 0.0, 1.0);
}

// An ellipse's signed distance, near enough: its implicit value over its gradient.
fn ellipse_dist(p: vec2<f32>, c: vec4<f32>) -> f32 {
    let q = (p - c.xy) / c.zw;
    let g = length(q / c.zw);
    return (length(q) - 1.0) * length(q) / max(g, 1e-6);
}

fn paint(pr: Prim, p: vec2<f32>) -> vec4<f32> {
    if pr.kind.y == 0u {
        return pr.colors[0];
    }
    let d = pr.grad.zw - pr.grad.xy;
    let t = clamp(dot(p - pr.grad.xy, d) / max(dot(d, d), 1e-9), 0.0, 1.0);
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

fn sample(tex: u32, uv: vec2<f32>) -> vec4<f32> {
    switch tex {
        case 0u: { return textureSampleLevel(lobby, smooth_px, uv / vec2<f32>(textureDimensions(lobby)), 0.0); }
        case 1u: { return textureSampleLevel(atlas, smooth_px, uv / vec2<f32>(textureDimensions(atlas)), 0.0); }
        case 2u: { return textureSampleLevel(wash, smooth_px, uv / vec2<f32>(textureDimensions(wash)), 0.0); }
        case 3u: { return textureSampleLevel(layer_a, smooth_px, uv / vec2<f32>(textureDimensions(layer_a)), 0.0); }
        default: { return textureSampleLevel(layer_b, smooth_px, uv / vec2<f32>(textureDimensions(layer_b)), 0.0); }
    }
}

fn picture(pr: Prim, p: vec2<f32>) -> vec4<f32> {
    let l = vec2(pr.xf.x * p.x + pr.xf.z * p.y + pr.xf2.x, pr.xf.y * p.x + pr.xf.w * p.y + pr.xf2.y);
    let r = pr.s0;
    let edge = min(min(l.x - r.x, r.z - l.x), min(l.y - r.y, r.w - l.y)) * pr.xf2.z;
    let cover = clamp(edge + 0.5, 0.0, 1.0);
    if cover <= 0.0 {
        return vec4(0.0);
    }
    // Held inside the picture's own texels, as Qt samples a picture's edge.
    let k = clamp((l - r.xy) / (r.zw - r.xy), vec2(0.0), vec2(1.0));
    let uv = clamp(pr.s1.xy + k * pr.s1.zw, pr.s1.xy + 0.5, pr.s1.xy + pr.s1.zw - 0.5);
    let texel = sample(pr.kind.w, uv);
    if pr.kind.y == 3u {
        return pr.colors[0] * texel.a * cover;
    }
    return texel * pr.colors[0].a * cover;
}

@fragment
fn fs(in: Out) -> @location(0) vec4<f32> {
    let pr = prims[in.index];
    let p = in.pos.xy;
    let c = pr.clip;
    let inside = clamp(min(min(p.x - c.x, c.z - p.x), min(p.y - c.y, c.w - p.y)) + 0.5, 0.0, 1.0);
    var cover = 1.0;
    switch pr.kind.x {
        case 0u: {
            let r = pr.s0;
            cover = clamp(min(min(p.x - r.x, r.z - p.x), min(p.y - r.y, r.w - p.y)) + 0.5, 0.0, 1.0);
        }
        case 1u: { cover = clamp(0.5 - ellipse_dist(p, pr.s0), 0.0, 1.0); }
        case 2u: { cover = polygon(p, u32(pr.s0.x), u32(pr.s0.y)); }
        case 3u: { cover = stroke(p, u32(pr.s0.x), u32(pr.s0.y), pr.s0.z, pr.s0.w > 0.5); }
        case 4u: { return picture(pr, p) * inside; }
        case 5u: {
            let h = pr.s1.x;
            let d = abs(ellipse_dist(p, pr.s0));
            cover = select(clamp(h + 0.5 - d, 0.0, 1.0), clamp(1.0 - d, 0.0, 1.0) * h * 2.0, h < 0.5);
        }
        default: {}
    }
    return paint(pr, p) * cover * inside;
}
