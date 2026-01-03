package ai

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
	"time"
)

type MessagePayload struct {
	Platform    string `json:"platform"`
	RoomID      string `json:"room_id"`
	Sender      string `json:"sender"`
	SenderName  string `json:"sender_name"`
	IsGroup     bool   `json:"is_group"`
	Timestamp   int64  `json:"timestamp"`
	Text        string `json:"text"`
	MessageID   string `json:"message_id"`
}

var sidecarURL = "http://localhost:8080/message"

func Emit(payload MessagePayload) {
	data, err := json.Marshal(payload)
	if err != nil {
		log.Println("[AI] marshal error:", err)
		return
	}

	req, err := http.NewRequest(
		"POST",
		sidecarURL,
		bytes.NewBuffer(data),
	)
	if err != nil {
		log.Println("[AI] request error:", err)
		return
	}

	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{
		Timeout: 2 * time.Second,
	}

	resp, err := client.Do(req)
	if err != nil {
		log.Println("[AI] sidecar unreachable:", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		log.Println("[AI] sidecar returned", resp.Status)
	}
}
