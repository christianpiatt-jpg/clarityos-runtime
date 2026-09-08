// #161 -- the phone had no test script. Pure lib/ functions only (money,
// the row text, the sha fence); no React Native rendering here.
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts"],
  },
});
