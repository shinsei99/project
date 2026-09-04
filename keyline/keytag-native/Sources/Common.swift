import SwiftUI

/// 状態の札（保管中 / 貸出中 / 期限超過）。
struct StatusBadge: View {
    let text: String
    let kind: Kind

    enum Kind { case inStock, out, overdue

        var color: Color {
            switch self {
            case .inStock: return .green
            case .out: return .orange
            case .overdue: return .red
            }
        }
    }

    var body: some View {
        Text(text)
            .font(.caption).bold()
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(kind.color.opacity(0.15))
            .foregroundColor(kind.color)
            .clipShape(Capsule())
    }
}

/// 成功・失敗のひとこと。空文字なら何も出さない。
struct MessageLine: View {
    let text: String
    let isError: Bool

    var body: some View {
        if !text.isEmpty {
            Label(text, systemImage: isError ? "exclamationmark.triangle.fill" : "checkmark.circle.fill")
                .font(.footnote)
                .foregroundColor(isError ? .red : .green)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

/// 見出し付きの囲み。
struct Card<Content: View>: View {
    let title: String
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if !title.isEmpty {
                Text(title).font(.subheadline).bold().foregroundColor(.secondary)
            }
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

/// 項目名と値の1行。
struct FieldRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label).font(.footnote).foregroundColor(.secondary).frame(width: 78, alignment: .leading)
            Text(value.isEmpty ? "—" : value).font(.body)
            Spacer(minLength: 0)
        }
    }
}

extension Asset {
    var badgeKind: StatusBadge.Kind {
        if isOverdue { return .overdue }
        return isOut ? .out : .inStock
    }
    var badgeText: String { isOverdue ? "返却期限超過" : statusLabel }
}
