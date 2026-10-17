import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormProvider, useForm } from "react-hook-form";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VoiceInput } from "@/components/farmer/voice-input";
import { I18nProvider } from "@/lib/i18n";
import { reportFormDefaults, type ReportFormInput } from "@/lib/schemas/report";
import { installFakeMedia, removeFakeMedia } from "@/test/fake-media";

const HINDI = "मेरे टमाटर के पत्ते पीले हो रहे हैं";

function Harness({
  initial = "",
  onTranscribed,
}: {
  initial?: string;
  onTranscribed?: (transcript: string) => void;
}) {
  const form = useForm<ReportFormInput>({
    defaultValues: { ...reportFormDefaults, description: initial },
  });
  return (
    <I18nProvider>
      <FormProvider {...form}>
        <VoiceInput onTranscribed={onTranscribed} />
        <textarea aria-label="Description" {...form.register("description")} />
      </FormProvider>
    </I18nProvider>
  );
}

function respond(status: number, body: unknown) {
  return vi.fn<typeof fetch>(async () => new Response(JSON.stringify(body), { status }));
}

function sentLanguage(fetchMock: ReturnType<typeof respond>, call = 0): string | null {
  const init = fetchMock.mock.calls[call][1] as RequestInit;
  return (init.body as FormData).get("language") as string | null;
}

async function recordOnce(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /record a voice note|record again/i }));
  await user.click(await screen.findByRole("button", { name: "Stop" }));
}

beforeEach(() => window.localStorage.clear());
afterEach(removeFakeMedia);

describe("VoiceInput", () => {
  it("records, stops, transcribes in English and fills the description", async () => {
    const user = userEvent.setup();
    const { track } = installFakeMedia();
    const fetchMock = respond(200, { transcript: "Yellow spots on lower leaves.", language: "en-IN" });
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: /record a voice note/i }));
    expect(await screen.findByText("Recording")).toBeTruthy();
    expect(screen.getByTestId("voice-timer").textContent).toContain("/ 0:55");
    await user.click(screen.getByRole("button", { name: "Stop" }));

    await waitFor(() =>
      expect((screen.getByLabelText("Description") as HTMLTextAreaElement).value).toBe(
        "Yellow spots on lower leaves.",
      ),
    );
    expect(track.stop).toHaveBeenCalled();
    expect(sentLanguage(fetchMock)).toBe("auto");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/transcribe");
    expect(screen.getByText(/Yellow spots on lower leaves/, { selector: "p.italic" })).toBeTruthy();
  });

  it("asks the API to detect the language and hands the Hindi transcript on untranslated", async () => {
    window.localStorage.setItem("rootcause.language", "hi");
    const user = userEvent.setup();
    installFakeMedia();
    const fetchMock = respond(200, { transcript: HINDI, language: "hi-IN" });
    vi.stubGlobal("fetch", fetchMock);
    const onTranscribed = vi.fn();
    render(<Harness onTranscribed={onTranscribed} />);

    expect(screen.queryByRole("button", { name: "हिन्दी" })).toBeNull();
    await user.click(await screen.findByRole("button", { name: /^आवाज़ में बताएँ/ }));
    await user.click(await screen.findByRole("button", { name: "रोकें" }));

    await waitFor(() => expect(onTranscribed).toHaveBeenCalledWith(HINDI));
    expect((screen.getByLabelText("Description") as HTMLTextAreaElement).value).toBe(HINDI);
    expect(sentLanguage(fetchMock)).toBe("auto");
  });

  it("explains an empty recording and does not call the API", async () => {
    const user = userEvent.setup();
    const { track } = installFakeMedia({ chunkBytes: 0 });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness />);

    await recordOnce(user);

    expect((await screen.findByRole("alert")).textContent).toMatch(/no sound was recorded/i);
    expect(track.stop).toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /record a voice note|record again/i })).toBeTruthy();
  });

  it("explains a blocked microphone and does not call the API", async () => {
    const user = userEvent.setup();
    installFakeMedia({
      getUserMedia: async () => {
        throw new DOMException("denied", "NotAllowedError");
      },
    });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: /record a voice note/i }));

    expect((await screen.findByRole("alert")).textContent).toMatch(/microphone access was blocked/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows a failure and retries the same recording", async () => {
    const user = userEvent.setup();
    installFakeMedia();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ error: { code: "transcription_failed", message: "x", details: [] } }),
          { status: 502 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ transcript: "Second time lucky.", language: "en-IN" }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness />);

    await recordOnce(user);
    expect((await screen.findByRole("alert")).textContent).toMatch(/couldn't turn the recording/i);
    await user.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() =>
      expect((screen.getByLabelText("Description") as HTMLTextAreaElement).value).toBe(
        "Second time lucky.",
      ),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const firstAudio = (fetchMock.mock.calls[0][1] as RequestInit).body as FormData;
    const secondAudio = (fetchMock.mock.calls[1][1] as RequestInit).body as FormData;
    expect((secondAudio.get("audio") as Blob).size).toBe((firstAudio.get("audio") as Blob).size);
  });

  it("does not offer a retry when voice input is not configured", async () => {
    const user = userEvent.setup();
    installFakeMedia();
    vi.stubGlobal(
      "fetch",
      respond(503, { error: { code: "transcription_unavailable", message: "x", details: [] } }),
    );
    render(<Harness />);

    await recordOnce(user);

    expect((await screen.findByRole("alert")).textContent).toMatch(/isn't available right now/i);
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("lets the farmer edit the transcribed text", async () => {
    const user = userEvent.setup();
    installFakeMedia();
    vi.stubGlobal("fetch", respond(200, { transcript: "Brown spots", language: "en-IN" }));
    render(<Harness />);

    await recordOnce(user);
    const textarea = screen.getByLabelText("Description") as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.value).toBe("Brown spots"));
    await user.type(textarea, " on older leaves.");

    expect(textarea.value).toBe("Brown spots on older leaves.");
  });

  it("adds a voice note after text the farmer already typed", async () => {
    const user = userEvent.setup();
    installFakeMedia();
    vi.stubGlobal("fetch", respond(200, { transcript: "Spreading fast.", language: "en-IN" }));
    render(<Harness initial="Started three days ago." />);
    const textarea = screen.getByLabelText("Description") as HTMLTextAreaElement;

    await recordOnce(user);

    await waitFor(() => expect(textarea.value).toBe("Started three days ago. Spreading fast."));
  });

  it("can cancel a recording without sending anything", async () => {
    const user = userEvent.setup();
    const { track } = installFakeMedia();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: /record a voice note/i }));
    await user.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(track.stop).toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /record a voice note/i })).toBeTruthy();
  });
});
