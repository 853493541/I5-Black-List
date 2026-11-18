// 霓虹都市's shapes and pictures, one instanced quad each, shaded per pixel: coverage from the exact
// distance to the shape's edge (antialiased like QPainter), pictures sampled from the atlas (bilinear
// where Qt smooths them), cut to the clip, and blended premultiplied over (or added to) what is below.

struct Prim {
    kind: vec4<u32>,
    bbox: vec4<f32>,
    s0: vec4<f32>,
    s1: vec4<f32>,
    s2: vec4<f32>,
    clip: vec4<f32>,
    color: vec4<f32>,
};

@group(0) @binding(0) var<storage, read> prims: array<Prim>;
@group(0) @binding(1) var<storage, read> points: array<vec2<f32>>;
@group(0) @binding(2) var lobby: texture_2d<f32>;
@group(0) @binding(3) var atlas: texture_2d<f32>;
@group(0) @binding(4) var<uniform> size: vec4<f32>;

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

// Coverage from a distance to a pen's middle, half its width: thin pens cover about their width.
fn pen(d: f32, half: f32) -> f32 {
    if half < 0.5 {
        return clamp(1.0 - (d - half), 0.0, 1.0) * clamp(1.0 - d, 0.0, 1.0) * half * 2.0;
    }
    return clamp(half + 0.5 - d, 0.0, 1.0);
}

fn disc(p: vec2<f32>, c: vec3<f32>) -> f32 {
    let d = distance(p, c.xy);
    if c.z < 0.7 {
        return clamp(1.0 - d, 0.0, 1.0) * min(1.0, 3.0 * c.z * c.z);
    }
    return clamp(c.z + 0.5 - d, 0.0, 1.0);
}

fn polygon(p: vec2<f32>, offset: u32, count: u32) -> f32 {
    var d = 1e9;
    var inside = false;
    for (var i = 0u; i < count; i++) {
        let a = points[offset + i];
        let b = points[offset + (i + 1u) % count];
        d = min(d, seg_dist(p, a, b));
        if (a.y > p.y) != (b.y > p.y) && p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x {
            inside = !inside;
        }
    }
    return select(clamp(0.5 - d, 0.0, 1.0), clamp(0.5 + d, 0.0, 1.0), inside);
}

fn stroke(p: vec2<f32>, offset: u32, count: u32, half: f32) -> f32 {
    var d = 1e9;
    for (var i = 0u; i + 1u < count; i++) {
        d = min(d, seg_dist(p, points[offset + i], points[offset + i + 1u]));
    }
    return pen(d, half);
}

fn line(p: vec2<f32>, ab: vec4<f32>, half: f32, reach: f32) -> f32 {
    let a = ab.xy;
    let b = ab.zw;
    let len = max(distance(a, b), 1e-6);
    let u = (b - a) / len;
    let d = p - (a + b) * 0.5;
    let along = abs(dot(d, u)) - len * 0.5 - reach;
    let across = abs(d.x * -u.y + d.y * u.x);
    return pen(across, half) * clamp(0.5 - along, 0.0, 1.0);
}

fn ring(p: vec2<f32>, c: vec4<f32>, arc: vec4<f32>) -> f32 {
    let q = p - c.xy;
    var cover = pen(abs(length(q) - c.z), c.w);
    if arc.y < 7.0 {
        // Qt's angles run counterclockwise with y up.
        let tau = 6.2831853;
        let a = atan2(-q.y, q.x);
        let k = ((a - arc.x) % tau + tau) % tau;
        cover *= select(0.0, 1.0, k <= arc.y);
    }
    return cover;
}

fn texel(at: vec2<i32>, lo: vec2<i32>, hi: vec2<i32>) -> vec4<f32> {
    return textureLoad(atlas, clamp(at, lo, hi), 0);
}

fn picture(pr: Prim, p: vec2<f32>) -> vec4<f32> {
    let o = pr.s0.xy;
    let ax = pr.s0.zw;
    let ay = pr.s1.xy;
    let det = ax.x * ay.y - ax.y * ay.x;
    let q = p - o;
    let uv = vec2((q.x * ay.y - q.y * ay.x) / det, (ax.x * q.y - ax.y * q.x) / det);
    let span = vec2(length(ax), length(ay));
    let edge = min(uv, 1.0 - uv) * span;
    let cover = clamp(edge.x + 0.5, 0.0, 1.0) * clamp(edge.y + 0.5, 0.0, 1.0);
    if cover <= 0.0 {
        return vec4(0.0);
    }
    let src = pr.s1.zw;
    let lo = vec2<i32>(pr.s2.xy);
    let hi = lo + vec2<i32>(src) - 1;
    let t = uv * src;
    var c: vec4<f32>;
    if pr.kind.y == 1u {
        let f = t - 0.5;
        let i = vec2<i32>(floor(f)) + lo;
        let k = f - floor(f);
        let top = mix(texel(i, lo, hi), texel(i + vec2(1, 0), lo, hi), k.x);
        let bottom = mix(texel(i + vec2(0, 1), lo, hi), texel(i + vec2(1, 1), lo, hi), k.x);
        c = mix(top, bottom, k.y);
    } else {
        c = texel(vec2<i32>(floor(t)) + lo, lo, hi);
    }
    return c * pr.color.a * cover;
}

@fragment
fn fs(in: Out) -> @location(0) vec4<f32> {
    let pr = prims[in.index];
    let p = in.pos.xy;
    let cl = pr.clip;
    let inside = clamp(min(min(p.x - cl.x, cl.z - p.x), min(p.y - cl.y, cl.w - p.y)) + 0.5, 0.0, 1.0);
    var cover = 1.0;
    switch pr.kind.x {
        case 0u: { cover = clamp(min(min(p.x - pr.s0.x, pr.s0.z - p.x), min(p.y - pr.s0.y, pr.s0.w - p.y)) + 0.5, 0.0, 1.0); }
        case 1u: { cover = disc(p, pr.s0.xyz); }
        case 2u: { cover = polygon(p, u32(pr.s0.x), u32(pr.s0.y)); }
        case 3u: { cover = stroke(p, u32(pr.s0.x), u32(pr.s0.y), pr.s0.z); }
        case 4u: { cover = line(p, pr.s0, pr.s1.x, pr.s1.y); }
        case 5u: { cover = ring(p, pr.s0, pr.s1); }
        case 6u: { return picture(pr, p) * inside; }
        case 7u: { return vec4(textureLoad(lobby, vec2<i32>(p), 0).rgb, 1.0); }
        default: {}
    }
    return pr.color * cover * inside;
}
