// Every shape of a frame, one instanced quad each, shaded per pixel: coverage from the exact
// distance to the shape's edge (antialiased like QPainter), color from its paint, blended
// premultiplied over what is below, in the order the Python painter draws.

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
@group(0) @binding(3) var galaxy: texture_2d<f32>;
@group(0) @binding(4) var<uniform> size: vec4<f32>;
@group(0) @binding(5) var atlas: texture_2d<f32>;
@group(0) @binding(6) var times: texture_2d<f32>;

// One pixel of a picture in the atlas, held to the picture's edge.
fn texel(o: vec2<f32>, wh: vec2<f32>, q: vec2<i32>) -> vec4<f32> {
    return textureLoad(atlas, vec2<i32>(o) + clamp(q, vec2<i32>(0), vec2<i32>(wh) - 1), 0);
}

// A picture sampled at img (its pixel units): nearest, or between four pixels as Qt's smooth drawing.
fn sample(o: vec2<f32>, wh: vec2<f32>, img: vec2<f32>, nearest: bool) -> vec4<f32> {
    if nearest {
        return texel(o, wh, vec2<i32>(floor(img)));
    }
    let f = img - 0.5;
    let b = floor(f);
    let k = f - b;
    let i = vec2<i32>(b);
    let top = mix(texel(o, wh, i), texel(o, wh, i + vec2(1, 0)), k.x);
    let low = mix(texel(o, wh, i + vec2(0, 1)), texel(o, wh, i + vec2(1, 1)), k.x);
    return mix(top, low, k.y);
}

// A baked picture laid on through an affine map: flags 1 nearest, 2 added (Qt's Plus), 4 shown
// where its pen has passed, 8 a second picture added, 16 cut to a mask's alpha, 32 only a diagonal
// band of it, 64 clipped to a circle.
fn image(pr: Prim, p: vec2<f32>) -> vec4<f32> {
    let img = vec2(dot(pr.s0.xy, p), dot(pr.s0.zw, p)) + pr.grad.xy;
    let wh = pr.grad.zw;
    if img.x < 0.0 || img.y < 0.0 || img.x > wh.x || img.y > wh.y {
        return vec4(0.0);
    }
    let flags = pr.kind.w;
    let nearest = (flags & 1u) != 0u;
    var c = sample(pr.s1.xy, wh, img, nearest) * pr.s1.z;
    if (flags & 8u) != 0u {
        c = min(c + sample(pr.s2.xy, wh, img, nearest) * pr.s2.z, vec4(1.0));
    }
    if (flags & 16u) != 0u {
        c *= sample(pr.stops.xy, wh, img, nearest).a;
    }
    if (flags & 4u) != 0u {
        let at = vec2<i32>(pr.s1.xy) + clamp(vec2<i32>(floor(img)), vec2<i32>(0), vec2<i32>(wh) - 1);
        c *= clamp((pr.stops.z - textureLoad(times, at, 0).r) * pr.stops.w + 0.5, 0.0, 1.0);
    }
    if (flags & 32u) != 0u {
        let n = pr.colors[0].y;
        let a = pr.colors[0].x - 0.07 * n;
        let k = clamp(dot(img - vec2(a), vec2(1.0)) / (0.28 * n), 0.0, 1.0);
        c *= 1.0 - abs(2.0 * k - 1.0);
    }
    if (flags & 64u) != 0u {
        c *= clamp(pr.colors[1].z + 0.5 - distance(p, pr.colors[1].xy), 0.0, 1.0);
    }
    c *= pr.s1.w;
    if (flags & 2u) != 0u {
        c.a = 0.0;
    }
    return c;
}

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

fn rounded_rect(p: vec2<f32>, r: vec4<f32>, radius: f32) -> f32 {
    let c = r.xy + r.zw * 0.5;
    let q = abs(p - c) - r.zw * 0.5 + radius;
    let d = length(max(q, vec2(0.0))) + min(max(q.x, q.y), 0.0) - radius;
    return clamp(0.5 - d, 0.0, 1.0);
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
            // The Wash's hole: 12 rounded rects rubbed out over the gap, each taking 62/255 of what is left.
            var keep = 1.0;
            for (var s = 0; s < 12; s++) {
                let grow = 40.0 * (1.0 - f32(s) / 11.0);
                let r = pr.s1 + vec4(-grow, -grow, 2.0 * grow, 2.0 * grow);
                keep *= 1.0 - 62.0 / 255.0 * rounded_rect(p, r, 14.0 + grow);
            }
            return textureLoad(galaxy, at, 0) * keep * pr.colors[0].a;
        }
        case 7u: { return image(pr, p); }
        default: {}
    }
    return paint(pr, p) * cover;
}
