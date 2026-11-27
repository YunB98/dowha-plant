// npm run build 앞뒤에 실행 (package.json prebuild / postbuild)
//   pre : 이전 빌드의 API 조회 캐시를 지운다 (항상 그 순간의 운영 내용으로 빌드)
//   post: 목록이 비었을 때 빌드를 통과시키려고 만든 자리표시 페이지(/cases/_/ 등)를 지운다 (lib/content.ts PLACEHOLDER)
import { existsSync, readdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const step = process.argv[2];

if (step === "pre") {
  rmSync(".next/cache/fetch-cache", { recursive: true, force: true });
} else if (step === "post") {
  const removed = [];
  for (const section of existsSync("out") ? readdirSync("out", { withFileTypes: true }) : []) {
    if (!section.isDirectory()) continue;
    const placeholder = join("out", section.name, "_");
    if (existsSync(placeholder)) {
      rmSync(placeholder, { recursive: true, force: true });
      removed.push(placeholder);
    }
  }
  if (removed.length) console.log(`자리표시 페이지 삭제: ${removed.join(", ")}`);
} else {
  throw new Error(`알 수 없는 단계: ${step}`);
}
