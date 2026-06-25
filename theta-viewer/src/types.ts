export interface SpaceNode {
  id: string;
  name: string;
  imageUrl: string;
  status: 'queued' | 'processing' | 'done' | 'error';
  progress: number;
  message: string;
  depthMap?: Float32Array;
  depthWidth?: number;
  depthHeight?: number;
}
