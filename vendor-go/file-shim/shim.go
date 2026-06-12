// Package fileshim exposes primitive file helpers for Freehold FFI.
package fileshim

import "os"

// ReadText reads a UTF-8/text file and returns its content as a string.
func ReadText(path string) (string, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(content), nil
}

// WriteText writes a string to a file, replacing existing content.
func WriteText(path string, content string) (bool, error) {
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		return false, err
	}
	return true, nil
}
