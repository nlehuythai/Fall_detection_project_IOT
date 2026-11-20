
import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import api from "../services/api";

const BOUNDARY = new TextEncoder().encode("--frame");
const HEADER_SEPARATOR = new Uint8Array([13, 10, 13, 10]);

function findBytes(data, pattern, start = 0) {
    for (let i = start; i <= data.length - pattern.length; i++) {
        let matched = true;

        for (let j = 0; j < pattern.length; j++) {
            if (data[i + j] !== pattern[j]) {
                matched = false;
                break;
            }
        }

        if (matched) return i;
    }

    return -1;
}

function LiveView({ householdId, cameraId, reloadKey, onStatusChange }) {
    const [frameUrl, setFrameUrl] = useState(null);
    const [status, setStatus] = useState("connecting");

    useEffect(() => {
        if (!householdId || !cameraId) return;

        const controller = new AbortController();
        let active = true;
        let currentUrl = null;

        const updateStatus = (nextStatus) => {
            if (!active) return;
            setStatus(nextStatus);
            onStatusChange?.(nextStatus);
        };

        const readStream = async () => {
            try {
                updateStatus("connecting");

                const token = localStorage.getItem("access_token");
                const baseURL = api.defaults.baseURL?.replace(/\/$/, "");

                if (!token) {
                    throw new Error("Phiên đăng nhập không hợp lệ");
                }

                if (!baseURL) {
                    throw new Error("Chưa cấu hình API URL");
                }

                const response = await fetch(
                    `${baseURL}/households/${householdId}/cameras/${cameraId}/stream`,
                    {
                        headers: {
                            Authorization: `Bearer ${token}`,
                        },
                        signal: controller.signal,
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        `HTTP ${response.status}: Không thể kết nối camera`
                    );
                }

                if (!response.body) {
                    throw new Error("Trình duyệt không hỗ trợ đọc stream");
                }

                const reader = response.body.getReader();
                let buffer = new Uint8Array(0);
                let receivedFrame = false;

                while (active) {
                    const { value, done } = await reader.read();

                    if (done) break;

                    const merged = new Uint8Array(
                        buffer.length + value.length
                    );

                    merged.set(buffer);
                    merged.set(value, buffer.length);
                    buffer = merged;

                    while (active) {
                        const boundaryIndex = findBytes(
                            buffer,
                            BOUNDARY
                        );

                        if (boundaryIndex === -1) {
                            // Giữ lại phần cuối để ghép với chunk tiếp theo
                            buffer = buffer.slice(
                                Math.max(0, buffer.length - BOUNDARY.length)
                            );
                            break;
                        }

                        const headerStart = boundaryIndex + BOUNDARY.length;

                        const headerEnd = findBytes(
                            buffer,
                            HEADER_SEPARATOR,
                            headerStart
                        );

                        if (headerEnd === -1) {
                            buffer = buffer.slice(boundaryIndex);
                            break;
                        }

                        const nextBoundary = findBytes(
                            buffer,
                            BOUNDARY,
                            headerEnd + HEADER_SEPARATOR.length
                        );

                        if (nextBoundary === -1) {
                            buffer = buffer.slice(boundaryIndex);
                            break;
                        }

                        let jpegEnd = nextBoundary;

                        // Bỏ CRLF nằm trước boundary tiếp theo
                        if (
                            jpegEnd >= 2 &&
                            buffer[jpegEnd - 2] === 13 &&
                            buffer[jpegEnd - 1] === 10
                        ) {
                            jpegEnd -= 2;
                        }

                        const jpegStart = headerEnd + HEADER_SEPARATOR.length;

                        if (jpegEnd > jpegStart) {
                            const jpegBytes = buffer.slice(
                                jpegStart,
                                jpegEnd
                            );

                            const blob = new Blob(
                                [jpegBytes],
                                { type: "image/jpeg" }
                            );

                            const nextUrl = URL.createObjectURL(blob);

                            if (currentUrl) {
                                URL.revokeObjectURL(currentUrl);
                            }

                            currentUrl = nextUrl;
                            setFrameUrl(nextUrl);

                            if (!receivedFrame) {
                                receivedFrame = true;
                                updateStatus("connected");
                            }
                        }

                        buffer = buffer.slice(nextBoundary);
                    }
                }

                if (active) {
                    updateStatus("error");
                }

            } catch (error) {
                if (error.name === "AbortError") return;

                console.error("Live View error:", error);
                updateStatus("error");
            }
        };

        readStream();

        return () => {
            active = false;
            controller.abort();

            if (currentUrl) {
                URL.revokeObjectURL(currentUrl);
            }
        };
    }, [householdId, cameraId, reloadKey]);

    if (status === "error") {
        return (
            <div className="flex min-h-[300px] flex-col items-center justify-center gap-3 bg-black text-white">
                <WifiOff size={36} className="text-red-400" />
                <p className="text-sm">Không thể nhận luồng video</p>
            </div>
        );
    }

    return (
        <div className="relative flex min-h-[300px] items-center justify-center bg-black">
            {frameUrl && (
                <img
                    src={frameUrl}
                    alt="Live camera"
                    className="max-h-[65vh] w-full object-contain"
                />
            )}

            {status === "connecting" && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/60">
                    <p className="text-sm text-white">
                        Đang kết nối camera...
                    </p>
                </div>
            )}
        </div>
    );
}

export default LiveView;
