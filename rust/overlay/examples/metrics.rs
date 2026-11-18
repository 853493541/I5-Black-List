//! Prints the Chinese face's metrics, to check them against QFontMetrics.
fn main() {
    let face = overlay::text::Face::system().expect("a Chinese face");
    for px in [12.0, 16.0, 18.0, 24.0] {
        println!("{px}: ascent {} descent {} height {} 示例 {}", face.ascent(px), face.descent(px), face.height(px), face.advance("示例", px));
    }
}
