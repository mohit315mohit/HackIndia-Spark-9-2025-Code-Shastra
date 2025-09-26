import { dataFolderLocation } from "../constants.js";
import fs from "fs";
import path from "path";

export const saveJSON = (fileName, data) => {
  if (!fs.existsSync(dataFolderLocation)) {
    fs.mkdirSync(dataFolderLocation);
  }
  const filePath = path.join(dataFolderLocation, fileName);
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
  return filePath;
};