import { Container } from "@/components/ui/Container";
import { Card } from "@/components/ui/Card";

const FEATURES = [
  {
    title: "主軸を決めてから比較する",
    body: "「どれが最強か」ではなく「Claude Code を軸に、足りない部分に何を足すか」。実務で意味があるのはこちらです。",
  },
  {
    title: "点数の根拠を書く",
    body: "5つの軸（自律性・出力の質・費用対効果・習得しやすさ・日本語）で共通評価。実際に何をどれだけ触ったかを併記します。",
  },
  {
    title: "成果物ではなく作り方を出す",
    body: "投げたプロンプト、できた機能、完成までの過程、その後の改善過程。真似できる形で公開します。",
  },
  {
    title: "つまずきを隠さない",
    body: "症状 → 原因 → 直し方。原因が分かっていないものは「未特定」と書きます。同じ穴に落ちないための記録です。",
  },
];

export function FeatureGrid() {
  return (
    <Container className="py-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map((f) => (
          <Card key={f.title}>
            <h3 className="font-semibold">{f.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted">{f.body}</p>
          </Card>
        ))}
      </div>
    </Container>
  );
}
