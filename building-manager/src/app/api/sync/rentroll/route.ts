import { NextResponse } from "next/server";
import { revalidatePath } from "next/cache";
import { runRentRollSync } from "@/lib/rentrollSync";

// Dropboxの「★要更新★」レントロール3本＋管理物件台帳を読み、Building/Room/Tenant/Ownerへupsert同期。
export async function POST() {
  try {
    const report = await runRentRollSync();
    revalidatePath("/");
    return NextResponse.json(report, { status: report.ok ? 200 : 207 });
  } catch (e) {
    return NextResponse.json(
      { ok: false, errors: [(e as Error).message] },
      { status: 500 },
    );
  }
}
