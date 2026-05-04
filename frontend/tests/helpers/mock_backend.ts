import http from "http";
import type { AddressInfo } from "net";

/**
 * Mock backend HTTP en puerto random. Cada test arranca su propio backend
 * y lo cierra al final para no compartir state entre tests.
 */
export interface MockBackend {
  url: string;
  close: () => Promise<void>;
}

export function startMockBackend(handler: http.RequestListener): Promise<MockBackend> {
  return new Promise((resolve, reject) => {
    const server = http.createServer(handler);
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address() as AddressInfo;
      resolve({
        url: `http://127.0.0.1:${addr.port}`,
        close: () =>
          new Promise<void>((r) => {
            server.closeAllConnections?.();
            server.close(() => r());
          }),
      });
    });
  });
}
