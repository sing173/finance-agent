export function getFileNameFromPath(filePath: string): string {
  return filePath.split(/[/\\]/).pop() || filePath;
}