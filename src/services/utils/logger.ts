const colors = {
  reset: "\x1b[0m",
  dim: "\x1b[2m",
  info: "\x1b[36m", // Cyan
  warn: "\x1b[33m", // Yellow
  error: "\x1b[31m", // Red
};

const getTimestamp = () => new Date().toISOString();

export const Logger = {
  info: (message: string, ...args: any[]) => {
    console.log(
      `${colors.dim}[${getTimestamp()}]${colors.reset} ${colors.info}[INFO]${colors.reset} ${message}`,
      ...args
    );
  },
  warn: (message: string, ...args: any[]) => {
    console.warn(
      `${colors.dim}[${getTimestamp()}]${colors.reset} ${colors.warn}[WARN]${colors.reset} ${message}`,
      ...args
    );
  },
  error: (message: string, ...args: any[]) => {
    console.error(
      `${colors.dim}[${getTimestamp()}]${colors.reset} ${colors.error}[ERROR]${colors.reset} ${message}`,
      ...args
    );
  },
};
