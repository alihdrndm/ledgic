/** Offline upload queue in IndexedDB. Blobs are kept until the full send flow succeeds. */

export interface QueuedCapture {
  id: string;
  orgId: string;
  locationId: string | null;
  blob: Blob;
  filename: string;
  contentType: "image/jpeg" | "application/pdf";
  channel: "photo" | "upload";
  createdAt: number;
}

const DB = "ledgic-capture";
const STORE = "queue";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") return reject(new Error("IndexedDB unavailable"));
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE, { keyPath: "id" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  try {
    return await new Promise<T>((resolve, reject) => {
      const t = db.transaction(STORE, mode);
      const req = run(t.objectStore(STORE));
      t.oncomplete = () => resolve(req.result);
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
  } finally {
    db.close();
  }
}

export const captureQueue = {
  add: (item: QueuedCapture) => tx("readwrite", (s) => s.put(item)).then(() => undefined),
  remove: (id: string) => tx("readwrite", (s) => s.delete(id)).then(() => undefined),
  all: () => tx<QueuedCapture[]>("readonly", (s) => s.getAll() as IDBRequest<QueuedCapture[]>),
};
