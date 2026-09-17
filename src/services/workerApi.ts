import { Project, ActivityLog } from '../types';

const API_BASE = 'http://127.0.0.1:8765';
let workerToken = '';
export async function initializeWorker() {
  workerToken = await window.electronAPI?.getWorkerToken?.() || '';
}
async function fetch(url: string, options: RequestInit = {}): Promise<Response> {
  if (!workerToken) await initializeWorker();
  return window.fetch(url, {...options, headers: {...options.headers, 'X-Worker-Token': workerToken}});
}
export async function requestWorker(path: string, options: RequestInit = {}): Promise<any> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options, headers: {'Content-Type': 'application/json', ...options.headers},
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || `Worker request failed (${response.status})`);
  return body;
}

export interface LiveSystemStatus {
  gpu: {
    name: string;
    load_percent: number;
    vram_used_mb: number;
    vram_total_mb: number;
    vram_percent: number;
    nvenc_supported: boolean;
    source: string;
  };
  cpu: {
    load_percent: number;
    cores: number;
  };
  ram: {
    used_gb: number;
    total_gb: number;
    percent: number;
  };
  disk: {
    drive: string;
    free_gb: number;
    total_gb: number;
    percent_used: number;
  };
  active_worker: {
    stage: string;
    active_model: string | null;
    sequential_pipeline: string;
  };
}

export interface MediaAudioTrack {
  id: number;
  stream_index: number;
  name: string;
  type: 'game' | 'mic' | 'backup';
  channels: number;
  sample_rate: number;
  codec: string;
}

export interface InspectedMediaResult {
  file_name: string;
  file_path: string;
  file_size_mb: number;
  duration_seconds: number;
  duration_formatted: string;
  resolution: string;
  fps: number;
  video_codec: string;
  audio_tracks: MediaAudioTrack[];
  total_audio_tracks: number;
  suggested_mapping: {
    game_track: number;
    mic_track: number;
    backup_track: number;
  };
}

export interface TranscribedDialogueItem {
  id: string;
  index: number;
  timestamp: string;
  start_seconds: number;
  end_seconds: number;
  target_duration_sec: number;
  original_text: string;
  confidence: number;
  emotion: 'Surprised' | 'Excited' | 'Angry' | 'Scared' | 'Vindicated' | 'Laughing' | 'Calm';
  intensity: 'low' | 'medium' | 'high';
  keep_scene: boolean;
  subtitle: boolean;
}

export interface TranscribeResult {
  status: string;
  detected_language: string;
  language_confidence: number;
  total_segments: number;
  transcript_path: string;
  emotion_path: string;
  lines: TranscribedDialogueItem[];
}

export interface DirectorEnglishLine {
  line_id: string;
  timestamp: string;
  start_seconds: number;
  end_seconds: number;
  original_hindi: string;
  english_rewrite: string;
  emotion: string;
  target_duration_sec: number;
  zoom: number;
  sfx: string | null;
  meme: string | null;
}

export interface DirectorAnalyzeResult {
  success: boolean;
  story_summary: string;
  story_map: any[];
  english_lines: DirectorEnglishLine[];
  edit_plan: any;
  status: string;
}

export async function fetchSystemStatus(): Promise<LiveSystemStatus | null> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 7000);
    const res = await fetch(`${API_BASE}/api/system/status`, {
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    return null;
  }
}

export async function checkWorkerHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function testGeminiApiKey(apiKey: string): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/gemini/test-connection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey }),
    });
    return await res.json();
  } catch (err) {
    return { success: false, message: `Could not reach local worker daemon: ${err}` };
  }
}

export async function inspectMedia(filePath: string): Promise<InspectedMediaResult | null> {
  try {
    const res = await fetch(`${API_BASE}/api/media/inspect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: filePath }),
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.media;
  } catch (err) {
    console.error('Failed to inspect media:', err);
    return null;
  }
}

export async function prepareSession(params: {
  filePath: string;
  projectId: string;
  projectName: string;
  gameTrack: number;
  micTrack: number;
}): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/api/media/prepare-session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_path: params.filePath,
        project_id: params.projectId,
        project_name: params.projectName,
        game_track: params.gameTrack,
        mic_track: params.micTrack,
      }),
    });
    return await res.json();
  } catch (err) {
    console.error('Failed to prepare session:', err);
    return null;
  }
}

export async function transcribeSpeech(projectId: string, modelSize: string = 'tiny'): Promise<TranscribeResult | null> {
  try {
    const res = await fetch(`${API_BASE}/api/speech/transcribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId,
        model_size: modelSize,
      }),
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.data;
  } catch (err) {
    console.error('Failed to transcribe speech:', err);
    return null;
  }
}

export async function runDirectorAnalysis(params: {
  projectId: string;
  apiKey?: string;
  mode?: string;
  modelName?: string;
}): Promise<DirectorAnalyzeResult | null> {
  try {
    const res = await fetch(`${API_BASE}/api/director/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: params.projectId,
        api_key: params.apiKey,
        mode: params.mode || 'Story',
        model_name: params.modelName || 'gemini-2.5-flash',
      }),
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.data;
  } catch (err) {
    console.error('Failed to run director analysis:', err);
    return null;
  }
}

// --- PHASE 4: VOICE DUBBING & AUDIO STREAMING API ---

export interface VoiceItem {
  id: string;
  index: number;
  name: string;
  languages: string[];
  gender: string;
  gaming_preset: string;
}

export interface VoiceDubResult {
  success: boolean;
  total_clips: number;
  combined_track: string;
  manifest_path: string;
  status: string;
}

export interface VoiceClipPreview {
  output_path: string;
  raw_duration_sec: number;
  final_duration_sec: number;
  target_duration_sec: number;
  tempo_factor: number;
  voice_index: number;
}

export async function fetchVoices(): Promise<VoiceItem[]> {
  try {
    const res = await fetch(`${API_BASE}/api/voice/voices`);
    if (!res.ok) return [];
    const json = await res.json();
    return json.voices || [];
  } catch (err) {
    console.error('Failed to fetch voices:', err);
    return [];
  }
}

export async function generateVoiceDub(
  projectId: string,
  voiceIndex: number = 0,
  matchTiming: boolean = true
): Promise<VoiceDubResult | null> {
  try {
    const res = await fetch(`${API_BASE}/api/voice/generate-dub`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId,
        voice_index: voiceIndex,
        match_timing: matchTiming,
      }),
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.data;
  } catch (err) {
    console.error('Failed to generate voice dub:', err);
    return null;
  }
}

export async function previewVoiceClip(
  text: string,
  targetDurationSec: number = 2.4,
  voiceIndex: number = 0
): Promise<VoiceClipPreview | null> {
  try {
    const res = await fetch(`${API_BASE}/api/voice/preview-clip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        target_duration_sec: targetDurationSec,
        voice_index: voiceIndex,
      }),
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.clip;
  } catch (err) {
    console.error('Failed to preview voice clip:', err);
    return null;
  }
}

export function getAudioClipUrl(projectId: string, lineId: string): string {
  return `${API_BASE}/api/voice/play?project_id=${encodeURIComponent(projectId)}&line_id=${encodeURIComponent(lineId)}&token=${encodeURIComponent(workerToken)}&t=${Date.now()}`;
}

export function getVoiceDubUrl(projectId: string): string {
  return `${API_BASE}/api/voice/play-dub?project_id=${encodeURIComponent(projectId)}&token=${encodeURIComponent(workerToken)}&t=${Date.now()}`;
}

export function getPreviewClipUrl(): string {
  return `${API_BASE}/api/voice/play-preview?token=${encodeURIComponent(workerToken)}&t=${Date.now()}`;
}

export interface ProjectBackendData {
  project_id: string;
  media: any;
  transcript: any;
  emotion: any;
  story_map: any;
  english_lines: any;
  edit_plan: any;
  voice_manifest: any;
  render_manifest: any;
}

export async function fetchProjectData(projectId: string): Promise<ProjectBackendData | null> {
  try {
    const res = await fetch(`${API_BASE}/api/project/data/${encodeURIComponent(projectId)}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch project data:', err);
    return null;
  }
}

// --- PHASE 5: MASTER VIDEO RENDERING (NVENC) API ---

export interface RenderJobStatus {
  job_id: string;
  project_id: string;
  preset: string;
  status: 'starting' | 'rendering' | 'completed' | 'error' | 'not_found';
  percent: number;
  current_frame: number;
  total_frames: number;
  fps: number;
  elapsed_sec: number;
  eta_sec: number;
  encoder: string;
  output_path: string | null;
  file_size_mb: number;
  error: string | null;
}

export async function probeBestEncoder(): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/api/render/probe-encoder`);
    if (!res.ok) return null;
    const json = await res.json();
    return json.best_encoder;
  } catch {
    return null;
  }
}

export async function startMasterRender(params: {
  projectId: string;
  preset?: string;
  encoder?: string;
  outputFilename?: string;
}): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/api/render/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: params.projectId,
        preset: params.preset || 'YouTube 1440p60',
        encoder: params.encoder,
        output_filename: params.outputFilename,
      }),
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.job_id;
  } catch (err) {
    console.error('Failed to start master render:', err);
    return null;
  }
}

export async function pollRenderStatus(jobId: string): Promise<RenderJobStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/api/render/status/${encodeURIComponent(jobId)}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('Failed to poll render status:', err);
    return null;
  }
}

export async function openRenderedFolder(filePath: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/render/open-folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: filePath }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export function getRenderedVideoUrl(projectId: string): string {
  return `${API_BASE}/api/render/play-video?project_id=${encodeURIComponent(projectId)}&token=${encodeURIComponent(workerToken)}&t=${Date.now()}`;
}

export function getProxyVideoUrl(projectId: string): string {
  return `${API_BASE}/api/media/proxy-video?project_id=${encodeURIComponent(projectId)}&token=${encodeURIComponent(workerToken)}&t=${Date.now()}`;
}

export async function fetchProjects(): Promise<Project[]> {
  try {
    const res = await fetch(`${API_BASE}/api/projects`);
    if (!res.ok) return [];
    const json = await res.json();
    return json.projects || [];
  } catch (err) {
    console.error('Failed to fetch real projects:', err);
    return [];
  }
}

export async function fetchActivityLogs(projectId?: string): Promise<ActivityLog[]> {
  try {
    const url = projectId 
      ? `${API_BASE}/api/system/activity-logs?project_id=${encodeURIComponent(projectId)}`
      : `${API_BASE}/api/system/activity-logs`;
    const res = await fetch(url);
    if (!res.ok) return [];
    const json = await res.json();
    return json.logs || [];
  } catch (err) {
    console.error('Failed to fetch activity logs:', err);
    return [];
  }
}

