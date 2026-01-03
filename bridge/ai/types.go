package ai

type MessagePayload struct {
	Platform   string `json:"platform"`
	RoomID     string `json:"room_id"`
	Sender     string `json:"sender"`
	SenderName string `json:"sender_name"`
	IsGroup    bool   `json:"is_group"`
	Timestamp  int64  `json:"timestamp"`
	Text       string `json:"text"`
	MessageID  string `json:"message_id"`
}
