// Every shape of a frame, one instanced quad each, shaded per pixel: coverage from the exact
// distance to the shape's edge (antialiased like QPainter), color from its paint, blended
// premultiplied over what is below, in the order the Python painter draws. 数学公式's copy of the
// spike's scene.wgsl: pictures from the atlas (smoothed, clipped), circle outlines, the paper's hole.

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
        case 7u: {
            // A picture, smoothed as QPainter's SmoothPixmapTransform does, inside its pixel clip.
            let c = pr.s2;
            if p.x < c.x || p.x >= c.z || p.y < c.y || p.y >= c.w || p.x < pr.s0.x || p.y < pr.s0.y || p.x >= pr.s0.x + pr.s0.z || p.y >= pr.s0.y + pr.s0.w {
                return vec4(0.0);
            }
            let texel = sample(pr, p);
            if (pr.kind.w & 1u) != 0u {
                cover = texel.a;
            } else {
                return texel * pr.colors[0].a * clip(pr, p);
            }
        }
        case 8u: {
            let d = abs(distance(p, pr.s0.xy) - pr.s0.z);
            cover = select(clamp(pr.s0.w + 0.5 - d, 0.0, 1.0), clamp(1.0 - d, 0.0, 1.0) * pr.s0.w * 2.0, pr.s0.w < 0.5);
        }
        default: {}
    }
    return paint(pr, p) * cover * clip(pr, p) * hole(pr, p);
}

fn sample(pr: Prim, p: vec2<f32>) -> vec4<f32> {
    let src = (p - pr.s0.xy) * pr.s1.zw / pr.s0.zw - 0.5;
    let f = fract(src);
    let base = vec2<i32>(floor(src));
    let lo = vec2<i32>(pr.s1.xy);
    let hi = lo + vec2<i32>(pr.s1.zw) - 1;
    let a = textureLoad(atlas, clamp(base, vec2(0), hi - lo) + lo, 0);
    let b = textureLoad(atlas, clamp(base + vec2(1, 0), vec2(0), hi - lo) + lo, 0);
    let c = textureLoad(atlas, clamp(base + vec2(0, 1), vec2(0), hi - lo) + lo, 0);
    let d = textureLoad(atlas, clamp(base + vec2(1, 1), vec2(0), hi - lo) + lo, 0);
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

fn clip(pr: Prim, p: vec2<f32>) -> f32 {
    if (pr.kind.w & 4u) == 0u {
        return 1.0;
    }
    return polygon(p, u32(pr.grad.x), u32(pr.grad.y));
}

// The paper's grid rubbed out over the names: an oval, gone in the middle, fading to its edge.
fn hole(pr: Prim, p: vec2<f32>) -> f32 {
    if (pr.kind.w & 2u) == 0u {
        return 1.0;
    }
    let d = length((p - vec2(0.535, 0.565) * size.xy) / (vec2(0.6, 0.5) * size.xy));
    return 1.0 - clamp((1.0 - d) / 0.38, 0.0, 1.0);
}
