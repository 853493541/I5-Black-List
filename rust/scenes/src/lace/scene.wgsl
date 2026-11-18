// Every shape of a frame, one instanced quad each, shaded per pixel: coverage from the exact
// distance to the shape's edge (antialiased like QPainter), color from its paint, blended
// premultiplied over what is below, in the order the Python painter draws. Copied from
// ../scene.wgsl and grown: strokes of several subpaths with any paint, clips, reflected gradients,
// pictures from the scene's layers and a smoothed (bilinear) atlas.

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
@group(0) @binding(3) var layer_a: texture_2d<f32>;
@group(0) @binding(4) var layer_b: texture_2d<f32>;
@group(0) @binding(5) var atlas: texture_2d<f32>;
@group(0) @binding(6) var<uniform> size: vec4<f32>;

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

fn is_break(i: u32, offset: u32, count: u32) -> bool {
    return i >= count || points[offset + i].x < -1e29;
}

// A pen of half-width `half` along the polylines from offset; a point far off to the left starts a new
// one. With `square` the outer end of each one's first and last segment is cut flat there (the CPU has
// already pushed it out by half); elsewhere the ends and joins are round.
fn stroke(p: vec2<f32>, offset: u32, count: u32, half: f32, square: bool) -> f32 {
    var d = 1e9;
    for (var i = 0u; i + 1u < count; i++) {
        let a = points[offset + i];
        let b = points[offset + i + 1u];
        if a.x < -1e29 || b.x < -1e29 {
            continue;
        }
        let ab = b - a;
        let len = max(length(ab), 1e-9);
        let along = dot(p - a, ab) / len;
        let across = abs(dot(p - a, vec2(-ab.y, ab.x)) / len);
        var sd = seg_dist(p, a, b) - half;
        if square && ((along < 0.0 && (i == 0u || is_break(i - 1u, offset, count))) || (along > len && is_break(i + 2u, offset, count))) {
            let e = vec2(select(along - len, -along, along < 0.0), across - half);
            sd = length(max(e, vec2(0.0))) + min(max(e.x, e.y), 0.0);
        }
        d = min(d, sd);
    }
    if half < 0.5 {
        return clamp(1.0 - (d + half), 0.0, 1.0) * half * 2.0;
    }
    return clamp(0.5 - d, 0.0, 1.0);
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
        if (pr.kind.w & 4u) != 0u {
            t = t - 2.0 * floor(t / 2.0);
            t = select(t, 2.0 - t, t > 1.0);
        }
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

// The atlas at a point in its own pixels, smoothed between its four nearest, clamped to the part `src`.
fn atlas_at(q: vec2<f32>, src: vec4<f32>) -> vec4<f32> {
    let hi = src.zw - 1.0;
    let f = q - 0.5;
    let base = floor(f);
    let w = f - base;
    let p0 = vec2<i32>(clamp(base, vec2(0.0), hi) + src.xy);
    let p1 = vec2<i32>(clamp(base + 1.0, vec2(0.0), hi) + src.xy);
    let top = mix(textureLoad(atlas, p0, 0), textureLoad(atlas, vec2(p1.x, p0.y), 0), w.x);
    let bottom = mix(textureLoad(atlas, vec2(p0.x, p1.y), 0), textureLoad(atlas, p1, 0), w.x);
    return mix(top, bottom, w.y);
}

fn picture(pr: Prim, p: vec2<f32>) -> vec4<f32> {
    let at = vec2<i32>(p);
    let which = u32(pr.s0.x);
    if which == 0u {
        return textureLoad(lobby, at, 0);
    }
    if which == 1u {
        return textureLoad(layer_a, at, 0) * pr.colors[0].a;
    }
    if which == 2u {
        return textureLoad(layer_b, at, 0) * pr.colors[0].a;
    }
    let dest = pr.s1;
    if p.x < dest.x || p.y < dest.y || p.x >= dest.x + dest.z || p.y >= dest.y + dest.w {
        return vec4(0.0);
    }
    let q = (p - dest.xy) / dest.zw * pr.grad.zw;
    return atlas_at(q, pr.grad) * pr.colors[0].a;
}

@fragment
fn fs(in: Out) -> @location(0) vec4<f32> {
    let pr = prims[in.index];
    let p = in.pos.xy;
    var cover = 1.0;
    var color: vec4<f32>;
    switch pr.kind.x {
        case 1u: { cover = disc(p, pr.s0.xyz); }
        case 2u: { cover = polygon(p, u32(pr.s0.x), u32(pr.s0.y)); }
        case 5u: { cover = stroke(p, u32(pr.s0.x), u32(pr.s0.y), pr.s0.z, pr.s0.w > 0.5); }
        default: {}
    }
    if pr.kind.x == 6u {
        color = picture(pr, p);
    } else {
        color = paint(pr, p);
    }
    let clip = pr.kind.w & 3u;
    if clip == 1u {
        cover *= 1.0 - rounded_rect(p, pr.s2, pr.s1.w);
    } else if clip == 2u {
        let r = pr.s2;
        if p.x < r.x || p.y < r.y || p.x >= r.x + r.z || p.y >= r.y + r.w {
            cover = 0.0;
        }
    }
    return color * cover;
}
