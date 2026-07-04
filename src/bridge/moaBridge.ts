/**
 * Android WebView 桥接接口
 * 遵循项目已有的 moaBridge 模式
 * 在 Android 壳中，window.moaBridge 由原生注入
 */

declare global {
  interface Window {
    moaBridge?: MoaBridgeInstance;
    [key: string]: unknown;
  }
}

interface MoaBridgeInstance {
  callNative: (method: string, paramsJson?: string) => void;
  [key: string]: unknown;
}

function callNative(method: string, params?: Record<string, unknown>) {
  const paramsJson = params ? JSON.stringify(params) : undefined;
  window.moaBridge?.callNative(method, paramsJson);
}

// ==================== STT / TTS ====================

interface STTResult {
  success: boolean;
  text?: string;
  message?: string;
}

export const startSTT = async (params: {
  lang?: string;
  cbFuncName?: string;
} = {}): Promise<STTResult> => {
  const cbFuncName = params.cbFuncName ?? 'onSTTResult';
  return new Promise((resolve) => {
    window[cbFuncName] = (data: unknown) => {
      if (data === undefined) return;
      const parsed = typeof data === 'string' ? JSON.parse(data) : data;
      resolve(parsed as STTResult);
      delete window[cbFuncName];
    };
    callNative('startSTT', {
      lang: params.lang ?? 'zh-CN',
      cbFuncName,
    });
  });
};

export const stopSTT = (): void => {
  callNative('stopSTT');
};

interface TTSParams {
  text: string;
  lang?: string;
  rate?: number;
}

export const playTTS = (params: TTSParams): void => {
  callNative('playTTS', {
    text: params.text,
    lang: params.lang ?? 'zh-CN',
    rate: params.rate ?? 1.0,
  });
};

export const stopTTS = (): void => {
  callNative('stopTTS');
};

// ==================== File ====================

interface FilePickResult {
  success: boolean;
  uri?: string;
  name?: string;
  mimeType?: string;
  content?: string;
  isImage?: boolean;
  dataUrl?: string;
  message?: string;
}

export const pickFile = async (params: {
  accept?: string;
  cbFuncName?: string;
} = {}): Promise<FilePickResult> => {
  const cbFuncName = params.cbFuncName ?? 'onFilePicked';
  return new Promise((resolve) => {
    window[cbFuncName] = (data: unknown) => {
      if (data === undefined) return;
      const parsed = typeof data === 'string' ? JSON.parse(data) : data;
      resolve(parsed as FilePickResult);
      delete window[cbFuncName];
    };
    callNative('pickFile', {
      accept: params.accept ?? '*/*',
      cbFuncName,
    });
  });
};

// ==================== Navigation ====================

export const goBack = (): void => {
  callNative('goBack');
};

export const setTitle = (title: string): void => {
  callNative('setTitle', { title });
};

// ==================== SafeArea ====================

interface SafeAreaResult {
  success: boolean;
  top?: number;
  bottom?: number;
}

export const getSafeArea = async (params: {
  cbFuncName?: string;
} = {}): Promise<SafeAreaResult> => {
  const cbFuncName = params.cbFuncName ?? 'onSafeAreaResult';
  return new Promise((resolve) => {
    window[cbFuncName] = (data: unknown) => {
      if (data === undefined) return;
      const parsed = typeof data === 'string' ? JSON.parse(data) : data;
      resolve(parsed as SafeAreaResult);
      delete window[cbFuncName];
    };
    callNative('getSafeArea', { cbFuncName });
  });
};

// ==================== Utils ====================

export const isBridgeAvailable = (): boolean => {
  return typeof window.moaBridge?.callNative === 'function';
};
