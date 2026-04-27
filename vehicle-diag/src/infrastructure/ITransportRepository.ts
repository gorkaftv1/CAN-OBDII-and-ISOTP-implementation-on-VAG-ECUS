export interface ITransportRepository {
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  sendCommand(command: string): Promise<string>;
  onFrame(callback: (frame: string) => void): () => void;
  isConnected(): boolean;
}
