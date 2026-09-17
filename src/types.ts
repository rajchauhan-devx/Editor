export type ProjectStatus = 
  | 'Imported'
  | 'Analyzing'
  | 'Plan Ready'
  | 'Preview Ready'
  | 'Ready to Export'
  | 'Completed';

export interface Project {
  id: string;
  name: string;
  game: string;
  status: ProjectStatus;
  duration: string;
  durationSeconds: number;
  sourceFile: string;
  resolution: string;
  fps: number;
  codec: string;
  audioTracks: {
    id: number;
    name: string;
    type: 'game' | 'mic' | 'backup';
    channels: number;
  }[];
  progress: number;
  lastActive: string;
  costEstimate: number;
  costBudget: number;
  currentTask?: string;
  proxySizeMb: number;
}

export interface StorySegment {
  id: string;
  start: string;
  end: string;
  startSeconds: number;
  endSeconds: number;
  event: 'intro' | 'cutscene' | 'combat' | 'funny_death' | 'reaction' | 'travel' | 'boss' | 'dialogue';
  action: 'keep' | 'compress' | 'protect_keep' | 'cut';
  english_voice?: string;
  subtitle: boolean;
  zoom?: number;
  sfx?: string;
  meme?: string;
  protected_story: boolean;
  notes?: string;
}

export interface DialogueLine {
  id: string;
  timestamp: string;
  timestampSeconds: number;
  originalText: string;
  englishRewrite: string;
  emotion: 'Surprised' | 'Excited' | 'Angry' | 'Scared' | 'Vindicated' | 'Laughing' | 'Calm';
  targetDurationSec: number;
  intensity: 'low' | 'medium' | 'high';
  keepScene: boolean;
  subtitle: boolean;
  memeTag?: string;
  zoomTag?: string;
}

export interface AssetItem {
  id: string;
  name: string;
  classType: 'meme' | 'sfx' | 'music' | 'overlay';
  tags: string[];
  duration: string;
  cooldown: number; // in seconds
  seriousSceneProhibited: boolean;
  thumbnailUrl?: string;
}

export interface AIModelStatus {
  id: string;
  name: string;
  role: string;
  state: 'idle' | 'running' | 'unloaded' | 'ready';
  vramMb: number;
  orderIndex: number;
  notes: string;
}

export interface ActivityLog {
  id: string;
  time: string;
  sender: 'Media' | 'Speech worker' | 'Video worker' | 'Gemini' | 'FFmpeg' | 'NVENC';
  message: string;
  type: 'info' | 'success' | 'warning' | 'director';
}
