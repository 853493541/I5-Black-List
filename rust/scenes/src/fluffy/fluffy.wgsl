// 毛茸茸's frame (the spike's scene.wgsl, with layers and pictures): every shape and picture, one
// instanced quad each, shaded per pixel: shapes antialiased from the exact distance to their edge,
// pictures sampled from the atlas as QPainter lays them (bilinear where turned or sized, whole
// pixels where only moved), all blended premultiplied in the Python painter's order.

struct Prim {
    kind: vec4<u32>,
    bbox: vec4<f32>,
    s0: vec4<f32>,
    s1: vec4<f32>,
    s2: vec4<f32>,
    grad: vec4<f32>,
    stops: vec4<f32>,
    colors: array<vec4<f32>, 4>,
};

@group(0) @binding(0) var<storage, read> prims: array<Prim>;
@group(0) @binding(1) var<storage, read> points: array<vec2<f32>>;
@group(0) @binding(2) var lobby: texture_2d<f32>;
@group(0) @binding(3) var page: texture_2d<f32>;
@group(0) @binding(4) var<uniform> size: vec4<f32>;
@group(0) @binding(5) var doodles: texture_2d<f32>;
@group(0) @binding(6) var atlas: texture_2d<f32>;

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

// Coverage of a pixel by a disc; a disc smaller than a pixel covers about its area.
fn disc(p: vec2<f32>, c: vec3<f32>) -> f32 {
    let d = distance(p, c.xy);
    if c.z < 0.7 {
        return clamp(1.0 - d, 0.0, 1.0) * min(1.0, 3.0 * c.z * c.z);
    }
    return clamp(c.z + 0.5 - d, 0.0, 1.0);
}

fn seg_dist(p: vec2<f32>, a: vec2<f32>, b: vec2<f32>) -> f32 {
    let ab = b - a;
    let k = clamp(dot(p - a, ab) / max(dot(ab, ab), 1e-9), 0.0, 1.0);
    return distance(p, a + ab * k);
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
    if half < 0.5 {
        return clamp(1.0 - d, 0.0, 1.0) * half * 2.0;
    }
    return clamp(half + 0.5 - d, 0.0, 1.0);
}

// One texel of a picture in the atlas, its edges repeated (Qt's bilinear fetch clamps to the picture).
fn texel(pr: Prim, q: vec2<i32>) -> vec4<f32> {
    let c = clamp(q, vec2(0), vec2<i32>(pr.s2.xy) - 1);
    return textureLoad(atlas, c + vec2<i32>(vec2(pr.s0.w, pr.s1.w)), 0);
}

fn picture(pr: Prim, p: vec2<f32>) -> vec4<f32> {
    let q = vec2(dot(pr.s0.xyz, vec3(p, 1.0)), dot(pr.s1.xyz, vec3(p, 1.0)));
    var c: vec4<f32>;
    var cover = 1.0;
    if (pr.kind.y & 1u) != 0u {
        c = texel(pr, vec2<i32>(floor(q)));
    } else {
        let s = q - 0.5;
        let i = vec2<i32>(floor(s));
        let f = s - floor(s);
        let top = mix(texel(pr, i), texel(pr, i + vec2(1, 0)), f.x);
        let bottom = mix(texel(pr, i + vec2(0, 1)), texel(pr, i + vec2(1, 1)), f.x);
        c = mix(top, bottom, f.y);
        let inside = min(min(q.x, pr.s2.x - q.x), min(q.y, pr.s2.y - q.y));
        cover = clamp(inside * pr.s2.w + 0.5, 0.0, 1.0);
    }
    if (pr.kind.y & 2u) != 0u {
        // A clip rect under a turned painter: antialiased like a clip path.
        let k = vec2(dot(pr.grad.xyz, vec3(p, 1.0)), dot(pr.stops.xyz, vec3(p, 1.0)));
        let r = pr.colors[0];
        let d = min(min(k.x - r.x, r.z - k.x), min(k.y - r.y, r.w - k.y));
        cover *= clamp(d + 0.5, 0.0, 1.0);
    }
    return c * cover * pr.s2.z;
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

@fragment
fn fs(in: Out) -> @location(0) vec4<f32> {
    let pr = prims[in.index];
    let p = in.pos.xy;
    var cover = 1.0;
    switch pr.kind.x {
        case 1u: { cover = disc(p, pr.s0.xyz); }
        case 2u: { cover = polygon(p, u32(pr.s0.x), u32(pr.s0.y)); }
        case 3u: { cover = disc(p, pr.s0.xyz) * (1.0 - disc(p, pr.s1.xyz)); }
        case 4u: { cover = disc(p, pr.s0.xyz) * disc(p, pr.s1.xyz) * (1.0 - disc(p, pr.s2.xyz)); }
        case 5u: { cover = stroke(p, u32(pr.s0.x), u32(pr.s0.y), pr.s0.z); }
        case 6u: {
            let at = vec2<i32>(p);
            if pr.s0.x < 0.5 {
                return vec4(textureLoad(lobby, at, 0).rgb, 1.0);
            }
            if pr.s0.x < 1.5 {
                return textureLoad(page, at, 0) * pr.colors[0].a;
            }
            return textureLoad(doodles, at, 0) * pr.colors[0].a;
        }
        case 7u: { return picture(pr, p); }
        default: {}
    }
    return paint(pr, p) * cover;
}
