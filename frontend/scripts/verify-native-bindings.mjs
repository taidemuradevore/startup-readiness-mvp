import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { join } from "node:path";
import process from "node:process";

const require = createRequire(import.meta.url);

const nativePackageByPlatformArch = {
  "darwin:arm64": "lightningcss-darwin-arm64",
  "darwin:x64": "lightningcss-darwin-x64",
  "linux:arm64": "lightningcss-linux-arm64-gnu",
  "linux:x64": "lightningcss-linux-x64-gnu",
  "win32:x64": "lightningcss-win32-x64-msvc",
  "win32:arm64": "lightningcss-win32-arm64-msvc",
};

const key = `${process.platform}:${process.arch}`;
const expectedPackage = nativePackageByPlatformArch[key];

function packageDir(packageName) {
  return join(process.cwd(), "node_modules", packageName);
}

try {
  require("lightningcss");
  process.exit(0);
} catch (error) {
  if (!expectedPackage) {
    console.error(`lightningcss native binding check failed on unsupported platform ${key}.`);
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }

  const expectedPath = packageDir(expectedPackage);
  console.error(`Cannot load lightningcss native binding for ${key}.`);
  console.error(`Expected package: ${expectedPackage}`);
  console.error(`Expected path: ${expectedPath}`);
  console.error(`Package present: ${existsSync(expectedPath) ? "yes" : "no"}`);
  console.error("");
  console.error("Fix the local install with:");
  console.error("  rm -rf node_modules package-lock.json");
  console.error("  npm --cache /private/tmp/startup-readiness-npm-cache install");
  console.error("");
  console.error("If this keeps switching between darwin-x64 and darwin-arm64, use one Node install consistently.");
  console.error(`Current Node: ${process.version} ${key}`);
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
