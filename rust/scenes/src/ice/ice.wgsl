// 冰蓝极光's shapes (copied from scene.wgsl and widened): every shape one instanced quad, shaded per
// pixel, coverage from the exact distance to its edge, up to 8 gradient stops, an optional clip to
// the heart, and pictures laid on smoothly (the aurora, the glass, the light inside the heart).

struct Prim {
    kind: vec4<u32>,
    bbox: vec4<f32>,
    s0: vec4<f32>,
    s1: vec4<f32>,
    s2: vec4<f32>,
    grad: vec4<f32>,
    stops: array<vec4<f32>, 2>,
    clip: vec4<f32>,
    colors: array<vec4<f32>, 8>,
};

@group(0) @binding(0) var<storage, read> prims: array<Prim>;
@group(0) @binding(1) var<storage, read> points: array<vec2<f32>>;
@group(0) @binding(2) var lobby: texture_2d<f32>;
@group(0) @binding(3) var wash: texture_2d<f32>;
@group(0) @binding(4) var aurora: texture_2d<f32>;
@group(0) @binding(5) var glass: texture_2d<f32>;
@group(0) @binding(6) var within: texture_2d<f32>;
@group(0) @binding(7) var<uniform> size: vec4<f32>;
@group(0) @binding(8) var soft: sampler;

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

fn segments(p: vec2<f32>, offset: u32, count: u32, half: f32) -> f32 {
    var d = 1e9;
    for (var i = 0u; i + 1u < count; i += 2u) {
        d = min(d, seg_dist(p, points[offset + i], points[offset + i + 1u]));
    }
    if half < 0.5 {
        return clamp(1.0 - d, 0.0, 1.0) * half * 2.0;
    }
    return clamp(half + 0.5 - d, 0.0, 1.0);
}

fn stop_at(pr: Prim, i: u32) -> f32 {
    return pr.stops[i / 4u][i % 4u];
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
        let a = stop_at(pr, i - 1u);
        if t >= a {
            let span = stop_at(pr, i) - a;
            c = mix(pr.colors[i - 1u], pr.colors[i], select(clamp((t - a) / span, 0.0, 1.0), 1.0, span <= 0.0));
        }
    }
    return c;
}

// A picture laid smoothly into the rect s1 (x, y, w, h).
fn picture(pr: Prim, p: vec2<f32>) -> vec4<f32> {
    let uv = (p - pr.s1.xy) / pr.s1.zw;
    if any(uv < vec2(0.0)) || any(uv > vec2(1.0)) {
        return vec4(0.0);
    }
    let layer = u32(pr.s0.x);
    var c: vec4<f32>;
    if layer == 2u {
        c = textureSampleLevel(aurora, soft, uv, 0.0);
    } else if layer == 3u {
        c = textureSampleLevel(glass, soft, uv, 0.0);
    } else {
        c = textureSampleLevel(within, soft, uv, 0.0);
    }
    return c * pr.colors[0].a;
}

@fragment
fn fs(in: Out) -> @location(0) vec4<f32> {
    let pr = prims[in.index];
    let p = in.pos.xy;
    var cover = 1.0;
    if (pr.kind.w & 1u) != 0u {
        cover = polygon(p, u32(pr.clip.x), u32(pr.clip.y));
    }
    switch pr.kind.x {
        case 1u: { cover *= disc(p, pr.s0.xyz); }
        case 2u: { cover *= polygon(p, u32(pr.s0.x), u32(pr.s0.y)); }
        case 5u: { cover *= stroke(p, u32(pr.s0.x), u32(pr.s0.y), pr.s0.z); }
        case 7u: { cover *= segments(p, u32(pr.s0.x), u32(pr.s0.y), pr.s0.z); }
        case 6u: {
            let at = vec2<i32>(p);
            if pr.s0.x < 0.5 {
                return vec4(textureLoad(lobby, at, 0).rgb, 1.0);
            }
            if pr.s0.x > 1.5 {
                return picture(pr, p) * cover;
            }
            // The Wash's hole: 12 rounded rects rubbed out over the gap, each taking 62/255 of what is left.
            var keep = 1.0;
            for (var s = 0; s < 12; s++) {
                let grow = 40.0 * (1.0 - f32(s) / 11.0);
                let r = pr.s1 + vec4(-grow, -grow, 2.0 * grow, 2.0 * grow);
                keep *= 1.0 - 62.0 / 255.0 * rounded_rect(p, r, 14.0 + grow);
            }
            return textureLoad(wash, at, 0) * keep * pr.colors[0].a;
        }
        default: {}
    }
    return paint(pr, p) * cover;
}
