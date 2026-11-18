// 竖琴清风's frames: each thing laid on is a quad; every pixel of it is shaded here. Pictures are sampled
// bilinearly through the inverse of their transform (transparent outside, as Qt draws a turned image),
// soft dots are lyre.py's radial gradient, and everything is blended premultiplied in the painter's order.

struct Quad {
    m: vec4<f32>,     // a b c d: x' = a x + c y + e, y' = b x + d y + f
    n: vec4<f32>,     // e f, picture width and height (a dot: centre x, y, radius)
    color: vec4<f32>, // a dot's color; w: opacity
    kind: vec4<f32>,  // x: 0 picture, 1 dot, 2 the lobby; y: clip channel (0 none)
};

@group(0) @binding(0) var<uniform> screen: vec4<f32>;
@group(0) @binding(1) var<storage, read> quads: array<Quad>;
@group(0) @binding(2) var lobby: texture_2d<f32>;
@group(0) @binding(3) var clips: texture_2d<f32>;
@group(1) @binding(0) var pic: texture_2d<f32>;

struct Out {
    @builtin(position) pos: vec4<f32>,
    @location(0) @interpolate(flat) index: u32,
};

@vertex
fn vs(@builtin(vertex_index) v: u32, @builtin(instance_index) i: u32) -> Out {
    let q = quads[i];
    let corner = vec2<f32>(f32(v == 1u || v == 2u || v == 4u), f32(v == 2u || v == 4u || v == 5u));
    var p: vec2<f32>;
    if q.kind.x == 2.0 {
        p = corner * screen.xy;
    } else if q.kind.x == 1.0 {
        p = q.n.xy + (corner * 2.0 - 1.0) * (q.n.z + 1.0);
    } else {
        let local = corner * (q.n.zw + 2.0) - 1.0;
        p = vec2<f32>(q.m.x * local.x + q.m.z * local.y + q.n.x, q.m.y * local.x + q.m.w * local.y + q.n.y);
    }
    var out: Out;
    out.pos = vec4<f32>(p.x / screen.x * 2.0 - 1.0, 1.0 - p.y / screen.y * 2.0, 0.0, 1.0);
    out.index = i;
    return out;
}

fn texel(x: i32, y: i32, size: vec2<i32>) -> vec4<f32> {
    if x < 0 || y < 0 || x >= size.x || y >= size.y {
        return vec4<f32>(0.0);
    }
    return textureLoad(pic, vec2<i32>(x, y), 0);
}

@fragment
fn fs(in: Out) -> @location(0) vec4<f32> {
    let q = quads[in.index];
    let at = in.pos.xy;
    var c: vec4<f32>;
    if q.kind.x == 2.0 {
        return textureLoad(lobby, vec2<i32>(at), 0);
    } else if q.kind.x == 1.0 {
        let d = distance(at, q.n.xy);
        let r = q.n.z;
        let k = d / r;
        var a = mix(q.color.w * 0.35, 0.0, clamp((k - 0.35) / 0.65, 0.0, 1.0));
        if k < 0.35 {
            a = mix(q.color.w, q.color.w * 0.35, k / 0.35);
        }
        a = a * clamp(r - d + 0.5, 0.0, 1.0);
        c = vec4<f32>(q.color.rgb * a, a);
    } else {
        let det = q.m.x * q.m.w - q.m.y * q.m.z;
        let rel = at - q.n.xy;
        let u = (q.m.w * rel.x - q.m.z * rel.y) / det - 0.5;
        let v = (-q.m.y * rel.x + q.m.x * rel.y) / det - 0.5;
        let size = vec2<i32>(textureDimensions(pic));
        let x0 = i32(floor(u));
        let y0 = i32(floor(v));
        let fx = u - floor(u);
        let fy = v - floor(v);
        let top = mix(texel(x0, y0, size), texel(x0 + 1, y0, size), fx);
        let bottom = mix(texel(x0, y0 + 1, size), texel(x0 + 1, y0 + 1, size), fx);
        c = mix(top, bottom, fy) * q.color.w;
    }
    let ch = i32(q.kind.y);
    if ch > 0 {
        let k = textureLoad(clips, vec2<i32>(at), 0);
        c = c * k[ch - 1];
    }
    return c;
}
