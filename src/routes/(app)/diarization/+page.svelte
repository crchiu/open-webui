
<script lang="ts">
	import { diarizeAudio, type DiarizationResponse } from '$lib/apis/audio';

	let selectedFile: File | null = null;
	let language = '';
	let loading = false;
	let error = '';
	let result: DiarizationResponse | null = null;

	const MAX_FILE_SIZE = 20 * 1024 * 1024;

	function handleFileChange(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		selectedFile = input.files?.[0] ?? null;
		result = null;
		error = '';

		if (selectedFile && selectedFile.size > MAX_FILE_SIZE) {
			error = '音訊檔案不可超過 20 MB';
			selectedFile = null;
			input.value = '';
		}
	}

	function formatTime(seconds: number): string {
		const totalSeconds = Math.max(0, Math.floor(seconds));
		const minutes = Math.floor(totalSeconds / 60);
		const remaining = totalSeconds % 60;

		return `${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`;
	}

	function transcriptText(data: DiarizationResponse): string {
		return data.diarization
			.map(
				(item) =>
					`[${formatTime(item.start)} - ${formatTime(item.end)}] ${item.speaker}\n${item.text}`
			)
			.join('\n\n');
	}

	async function analyze() {
		if (!selectedFile || loading) return;

		loading = true;
		error = '';
		result = null;

		try {
			const token = localStorage.getItem('token');

			if (!token) {
				throw new Error('登入狀態已失效，請重新登入');
			}

			result = await diarizeAudio(
				token,
				selectedFile,
				language || undefined
			);

			if (!result || !Array.isArray(result.diarization)) {
				throw new Error('API 未回傳有效的語者逐字稿');
			}
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	}

	async function copyTranscript() {
		if (!result) return;

		try {
			await navigator.clipboard.writeText(transcriptText(result));
		} catch {
			error = '無法複製逐字稿，請確認瀏覽器的剪貼簿權限';
		}
	}

	function downloadFile(content: string, filename: string, mime: string) {
		const blob = new Blob([content], { type: mime });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');

		link.href = url;
		link.download = filename;
		document.body.appendChild(link);
		link.click();
		link.remove();

		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}

	function exportTXT() {
		if (!result) return;

		downloadFile(
			transcriptText(result),
			'diarization.txt',
			'text/plain;charset=utf-8'
		);
	}

	function exportJSON() {
		if (!result) return;

		downloadFile(
			JSON.stringify(result, null, 2),
			'diarization.json',
			'application/json;charset=utf-8'
		);
	}
</script>

<svelte:head>
	<title>語者分離與逐字稿 - Open WebUI</title>
</svelte:head>

<div class="h-full w-full overflow-y-auto">
	<div class="mx-auto max-w-4xl px-5 py-8 space-y-6">
		<div>
			<h1 class="text-2xl font-semibold">
				語者分離與逐字稿
			</h1>
			<p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
				整合 Faster-Whisper 與 Pyannote，辨識錄音內容及不同語者的發言時間。
			</p>
		</div>

		<div class="rounded-xl border border-gray-200 dark:border-gray-700 p-5 space-y-5">
			<div class="space-y-2">
				<label for="diarization-file" class="block text-sm font-medium">
					選擇音訊檔案
				</label>
				<input
					id="diarization-file"
					type="file"
					accept=".mp3,.wav,.m4a,.mp4,.webm,.ogg,.flac"
					on:change={handleFileChange}
					disabled={loading}
					class="block w-full text-sm"
				/>
				<p class="text-xs text-gray-500">
					單一檔案上限 20 MB，實際支援格式以後端音訊解碼能力為準。
				</p>
			</div>

			<div class="space-y-2">
				<label for="diarization-language" class="block text-sm font-medium">
					辨識語言
				</label>
				<select
					id="diarization-language"
					bind:value={language}
					disabled={loading}
					class="w-full rounded-lg border border-gray-300 bg-transparent px-3 py-2 text-sm dark:border-gray-600"
				>
					<option value="">自動偵測</option>
					<option value="zh">中文</option>
					<option value="en">英文</option>
					<option value="ja">日文</option>
				</select>
			</div>

			<button
				type="button"
				on:click={analyze}
				disabled={!selectedFile || loading}
				class="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-gray-100 dark:text-gray-900"
			>
				{loading ? '語音分析中…' : '開始語者分離'}
			</button>

			{#if error}
				<p role="alert" class="text-sm text-red-600 dark:text-red-400">
					{error}
				</p>
			{/if}
		</div>

		{#if result}
			<div class="rounded-xl border border-gray-200 dark:border-gray-700 p-5 space-y-5">
				<div class="flex flex-wrap items-center justify-between gap-3">
					<h2 class="text-lg font-semibold">分析結果</h2>

					<div class="flex flex-wrap gap-2">
						<button
							type="button"
							on:click={copyTranscript}
							class="rounded-lg border px-3 py-2 text-sm dark:border-gray-600"
						>
							複製逐字稿
						</button>

						<button
							type="button"
							on:click={exportTXT}
							class="rounded-lg border px-3 py-2 text-sm dark:border-gray-600"
						>
							匯出 TXT
						</button>

						<button
							type="button"
							on:click={exportJSON}
							class="rounded-lg border px-3 py-2 text-sm dark:border-gray-600"
						>
							匯出 JSON
						</button>
					</div>
				</div>

				<div class="flex flex-wrap gap-4 text-sm text-gray-600 dark:text-gray-300">
					<span>檔案：{result.filename}</span>
					<span>語言：{result.language ?? '未知'}</span>
					<span>預測語者數：{result.num_speakers}</span>
				</div>

				<div class="space-y-4">
					{#each result.diarization as segment, index}
						<div
							class="rounded-lg bg-gray-50 p-4 dark:bg-gray-800/60"
						>
							<div class="mb-2 flex flex-wrap items-center gap-3">
								<span class="text-sm font-semibold">
									{segment.speaker}
								</span>
								<span class="text-xs text-gray-500 dark:text-gray-400">
									{formatTime(segment.start)}
									–
									{formatTime(segment.end)}
								</span>
							</div>

							<p class="whitespace-pre-wrap break-words text-sm leading-7">
								{segment.text}
							</p>
						</div>
					{:else}
						<p class="text-sm text-gray-500">未取得語者逐字稿。</p>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</div>
