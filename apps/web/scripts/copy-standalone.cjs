const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
for (const relative of [".next/static", "public"]) {
  const source = path.join(root, relative);
  if (fs.existsSync(source)) {
    fs.cpSync(source, path.join(root, ".next/standalone", relative), { recursive: true });
  }
}
