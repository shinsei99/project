import SwiftUI

/// 選択中の要素に出す「×」削除バッジ。
struct DeleteBadge: View {
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: "xmark")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(.white)
                .frame(width: 28, height: 28)
                .background(Circle().fill(Color.red))
                .overlay(Circle().stroke(.white, lineWidth: 1.5))
        }
        .buttonStyle(.plain)
    }
}

/// 拡大縮小ハンドル（見た目のみ。ジェスチャーは呼び出し側で付ける）。
struct ResizeBadge: View {
    var body: some View {
        Image(systemName: "arrow.up.left.and.arrow.down.right")
            .font(.system(size: 11, weight: .bold))
            .foregroundStyle(Color.accentColor)
            .frame(width: 28, height: 28)
            .background(Circle().fill(.white))
            .overlay(Circle().stroke(Color.accentColor, lineWidth: 2))
    }
}

/// 回転ハンドル（見た目のみ）。
struct RotateBadge: View {
    var body: some View {
        Image(systemName: "arrow.triangle.2.circlepath")
            .font(.system(size: 11, weight: .bold))
            .foregroundStyle(Color.accentColor)
            .frame(width: 28, height: 28)
            .background(Circle().fill(.white))
            .overlay(Circle().stroke(Color.accentColor, lineWidth: 2))
    }
}

/// 矢印の端点ハンドル（丸）。
struct EndpointBadge: View {
    var body: some View {
        Circle()
            .fill(Color.white)
            .overlay(Circle().stroke(Color.accentColor, lineWidth: 3))
            .frame(width: 26, height: 26)
            .shadow(color: .black.opacity(0.35), radius: 2, y: 1)
    }
}
