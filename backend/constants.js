import fs from "fs";
import path from "path";
const __dirname = path.resolve();

if (!fs.existsSync(path.join(__dirname, "../data"))) {
  fs.mkdirSync(path.join(__dirname, "../data"));
  console.log("Data folder created at:", path.join(__dirname, "../data"));
}

export const dataFolderLocation = path.join(__dirname, "../data");