import { AUDIO_API_BASE_URL } from '$lib/constants';

export const getAudioConfig = async (token: string) => {
	let error = null;

	const res = await fetch(`${AUDIO_API_BASE_URL}/config`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export type RealtimeConfig = {
	ENABLED: boolean;
	PROVIDER: 'openai' | 'azure';
	AUTH_TYPE: 'api_key' | 'microsoft_entra_id';
	OPENAI_API_BASE_URL: string;
	OPENAI_API_KEY: string;
	MODEL: string;
	VOICE: string;
	TRANSCRIPTION_MODEL: string;
	INPUT_PARAMS: Record<string, unknown> | null;
	REALTIME_CALL_PROMPT_TEMPLATE: string | null;
};

type AudioConfigForm = {
	tts: Record<string, unknown>;
	stt: Record<string, unknown>;
	realtime?: Partial<RealtimeConfig>;
};

export const updateAudioConfig = async (token: string, payload: AudioConfigForm) => {
	let error = null;

	const res = await fetch(`${AUDIO_API_BASE_URL}/config/update`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({
			...payload
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const transcribeAudio = async (token: string, file: File, language?: string) => {
	const data = new FormData();
	data.append('file', file);
	if (language) {
		data.append('language', language);
	}

	let error = null;
	const res = await fetch(`${AUDIO_API_BASE_URL}/transcriptions`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			authorization: `Bearer ${token}`
		},
		body: data
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};


export type DiarizationSegment = {
	speaker: string;
	start: number;
	end: number;
	text: string;
};

export type DiarizationResponse = {
	filename: string;
	language: string | null;
	text: string;
	speakers: string[];
	num_speakers: number;
	segments: {
		start: number;
		end: number;
		speaker: string;
	}[];
	diarization: DiarizationSegment[];
};

export const diarizeAudio = async (
	token: string,
	file: File,
	language?: string
): Promise<DiarizationResponse> => {
	const data = new FormData();

	data.append('file', file);

	if (language) {
		data.append('language', language);
	}

	const response = await fetch(
		`${AUDIO_API_BASE_URL}/diarize`,
		{
			method: 'POST',
			headers: {
				Accept: 'application/json',
				Authorization: `Bearer ${token}`
			},
			body: data
		}
	);

	if (!response.ok) {
		const error = await response.json().catch(() => null);
		throw new Error(
			error?.detail ?? `Diarization failed (${response.status})`
		);
	}

	return await response.json();
};


export const synthesizeOpenAISpeech = async (
	token: string = '',
	speaker: string = 'alloy',
	text: string = '',
	model?: string
) => {
	let error = null;

	const res = await fetch(`${AUDIO_API_BASE_URL}/speech`, {
		method: 'POST',
		headers: {
			Authorization: `Bearer ${token}`,
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({
			input: text,
			voice: speaker,
			...(model && { model })
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res;
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);

			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

interface AvailableModelsResponse {
	models: { name: string; id: string }[] | { id: string }[];
}

export const getModels = async (token: string = ''): Promise<AvailableModelsResponse> => {
	let error = null;

	const res = await fetch(`${AUDIO_API_BASE_URL}/models`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);

			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getVoices = async (token: string = '') => {
	let error = null;

	const res = await fetch(`${AUDIO_API_BASE_URL}/voices`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);

			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
