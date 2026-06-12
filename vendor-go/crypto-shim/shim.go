// Package cryptoshim exposes small crypto helpers for Freehold FFI.
package cryptoshim

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/sha512"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"unicode/utf16"
	"unsafe"
)

const (
	credTypeGeneric        = 1
	credentialTargetPrefix = "freehold/keepassxc/"
	keepassManagerService  = "KeePassManagerApp"
)

var (
	advapi32     = syscall.NewLazyDLL("advapi32.dll")
	procCredRead = advapi32.NewProc("CredReadW")
	procCredFree = advapi32.NewProc("CredFree")
)

type windowsCredential struct {
	Flags              uint32
	Type               uint32
	TargetName         *uint16
	Comment            *uint16
	LastWritten        syscall.Filetime
	CredentialBlobSize uint32
	CredentialBlob     *byte
	Persist            uint32
	AttributeCount     uint32
	Attributes         uintptr
	TargetAlias        *uint16
	UserName           *uint16
}

type keepassProfile struct {
	Password string `json:"password"`
	KeyPath  string `json:"key_path"`
}

type keepassEntryRow struct {
	Title    string
	Username string
	Notes    string
}

type KeePassXCCredential struct {
	Username       string
	Password       string
	WalletLocation string
}

// SHA256Hex returns the SHA-256 digest of text encoded as lowercase hex.
func SHA256Hex(text string) string {
	digest := sha256.Sum256([]byte(text))
	return hex.EncodeToString(digest[:])
}

// SHA512Hex returns the SHA-512 digest of text encoded as lowercase hex.
func SHA512Hex(text string) string {
	digest := sha512.Sum512([]byte(text))
	return hex.EncodeToString(digest[:])
}

// HMACSHA256Hex returns HMAC-SHA256(key, message) encoded as lowercase hex.
func HMACSHA256Hex(key string, message string) string {
	mac := hmac.New(sha256.New, []byte(key))
	mac.Write([]byte(message))
	return hex.EncodeToString(mac.Sum(nil))
}

// RandomHex returns byteCount cryptographically secure random bytes encoded as
// lowercase hex. byteCount must be between 0 and 4096 to keep FFI calls bounded.
func RandomHex(byteCount int64) (string, error) {
	if byteCount < 0 {
		return "", fmt.Errorf("byte count must be non-negative")
	}
	if byteCount > 4096 {
		return "", fmt.Errorf("byte count too large: %d", byteCount)
	}
	buffer := make([]byte, byteCount)
	if _, err := io.ReadFull(rand.Reader, buffer); err != nil {
		return "", err
	}
	return hex.EncodeToString(buffer), nil
}

// AES256GCMEncryptHex encrypts plaintext with AES-256-GCM. keyHex must encode
// exactly 32 bytes. aad is authenticated but not encrypted. The result is a hex
// encoded envelope: nonce || ciphertext || tag.
func AES256GCMEncryptHex(keyHex string, plaintext string, aad string) (string, error) {
	key, err := aes256Key(keyHex)
	if err != nil {
		return "", err
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", err
	}
	ciphertext := gcm.Seal(nil, nonce, []byte(plaintext), []byte(aad))
	envelope := append(nonce, ciphertext...)
	return hex.EncodeToString(envelope), nil
}

// AES256GCMDecryptHex decrypts an AES-256-GCM envelope produced by
// AES256GCMEncryptHex. keyHex must encode exactly 32 bytes and aad must match
// the authenticated data used for encryption.
func AES256GCMDecryptHex(keyHex string, envelopeHex string, aad string) (string, error) {
	key, err := aes256Key(keyHex)
	if err != nil {
		return "", err
	}
	envelope, err := hex.DecodeString(envelopeHex)
	if err != nil {
		return "", fmt.Errorf("decode envelope hex: %w", err)
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonceSize := gcm.NonceSize()
	if len(envelope) < nonceSize+gcm.Overhead() {
		return "", fmt.Errorf("ciphertext envelope too short")
	}
	nonce := envelope[:nonceSize]
	ciphertext := envelope[nonceSize:]
	plaintext, err := gcm.Open(nil, nonce, ciphertext, []byte(aad))
	if err != nil {
		return "", err
	}
	return string(plaintext), nil
}

func aes256Key(keyHex string) ([]byte, error) {
	key, err := hex.DecodeString(keyHex)
	if err != nil {
		return nil, fmt.Errorf("decode AES-256 key hex: %w", err)
	}
	if len(key) != 32 {
		return nil, fmt.Errorf("AES-256 key must be 32 bytes, got %d", len(key))
	}
	return key, nil
}

// KeePassXCCLIPath returns the resolved keepassxc-cli executable path.
func KeePassXCCLIPath() (string, error) {
	path, err := exec.LookPath("keepassxc-cli")
	if err != nil {
		return "", fmt.Errorf("keepassxc-cli not found on PATH: %w", err)
	}
	return path, nil
}

// KeePassXCVersion returns the keepassxc-cli version string.
func KeePassXCVersion() (string, error) {
	output, err := exec.Command("keepassxc-cli", "--version").CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("keepassxc-cli --version: %w: %s", err, strings.TrimSpace(string(output)))
	}
	return strings.TrimSpace(string(output)), nil
}

// KeePassXCGeneratePassword asks keepassxc-cli to generate a password using
// upper, lower, numeric and special character groups. The length is bounded to
// keep command execution predictable over the FFI boundary.
func KeePassXCGeneratePassword(length int64) (string, error) {
	if length < 8 {
		return "", fmt.Errorf("KeePassXC password length must be at least 8")
	}
	if length > 256 {
		return "", fmt.Errorf("KeePassXC password length too large: %d", length)
	}
	output, err := exec.Command(
		"keepassxc-cli",
		"generate",
		"--quiet",
		"--length", strconv.FormatInt(length, 10),
		"--lower",
		"--upper",
		"--numeric",
		"--special",
		"--every-group",
	).CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("keepassxc-cli generate: %w: %s", err, strings.TrimSpace(string(output)))
	}
	password := strings.TrimSpace(string(output))
	if password == "" {
		return "", fmt.Errorf("keepassxc-cli generated an empty password")
	}
	return password, nil
}

// KeePassXCListEntries reads the KeePass Manager profile from Windows
// Credential Manager, opens the database through keepassxc-cli, and returns a
// formatted table of entry title, username and notes. The master password is
// only passed to keepassxc-cli over stdin and is never returned to Freehold.
func KeePassXCListEntries(dbName string, maxEntries int64) (string, error) {
	dbName = strings.TrimSpace(dbName)
	if dbName == "" {
		return "", fmt.Errorf("KeePassXC database name/path must not be empty")
	}
	if maxEntries <= 0 {
		maxEntries = 500
	}
	if maxEntries > 1000 {
		return "", fmt.Errorf("KeePassXC max entries too large: %d", maxEntries)
	}
	profile, err := readKeePassManagerProfile(dbName)
	if err != nil {
		return "", err
	}
	paths, err := keepassxcListPaths(dbName, profile)
	if err != nil {
		return "", err
	}

	rows := make([]keepassEntryRow, 0, len(paths))
	for _, entryPath := range paths {
		if int64(len(rows)) >= maxEntries {
			break
		}
		row, err := keepassxcShowEntry(dbName, entryPath, profile)
		if err != nil {
			continue
		}
		rows = append(rows, row)
	}
	sort.Slice(rows, func(i int, j int) bool {
		return strings.ToLower(rows[i].Title) < strings.ToLower(rows[j].Title)
	})
	return formatKeePassRows(dbName, rows), nil
}

// KeePassXCEntryCredential reads one entry's username and password from a
// KeePassXC database. It is read-only: the database and Windows Credential
// Manager are only read, never modified.
func KeePassXCEntryCredential(keyringName string, dbFileName string, title string) (KeePassXCCredential, error) {
	keyringName = strings.TrimSpace(keyringName)
	dbFileName = strings.TrimSpace(dbFileName)
	title = strings.TrimSpace(title)
	if keyringName == "" {
		return KeePassXCCredential{}, fmt.Errorf("KeePassXC keyring/profile name must not be empty")
	}
	if dbFileName == "" {
		return KeePassXCCredential{}, fmt.Errorf("KeePassXC database filename must not be empty")
	}
	if title == "" {
		return KeePassXCCredential{}, fmt.Errorf("KeePassXC entry title must not be empty")
	}

	dbPath, err := resolveKeePassDBPath(dbFileName)
	if err != nil {
		return KeePassXCCredential{}, err
	}
	profile, err := readKeePassManagerProfileForKeyring(keyringName, dbPath)
	if err != nil {
		return KeePassXCCredential{}, err
	}

	credential, err := keepassxcShowCredential(dbPath, title, profile)
	if err == nil {
		if err := validateKeePassXCCredential(title, credential); err != nil {
			return KeePassXCCredential{}, err
		}
		return credential, nil
	}

	paths, listErr := keepassxcListPaths(dbPath, profile)
	if listErr != nil {
		return KeePassXCCredential{}, fmt.Errorf("KeePassXC entry %q not found directly and listing failed: %w", title, listErr)
	}
	for _, entryPath := range paths {
		if strings.EqualFold(filepath.Base(entryPath), title) {
			credential, err := keepassxcShowCredential(dbPath, entryPath, profile)
			if err != nil {
				return KeePassXCCredential{}, err
			}
			if err := validateKeePassXCCredential(title, credential); err != nil {
				return KeePassXCCredential{}, err
			}
			return credential, nil
		}
		row, rowErr := keepassxcShowEntry(dbPath, entryPath, profile)
		if rowErr == nil && strings.EqualFold(row.Title, title) {
			credential, err := keepassxcShowCredential(dbPath, entryPath, profile)
			if err != nil {
				return KeePassXCCredential{}, err
			}
			if err := validateKeePassXCCredential(title, credential); err != nil {
				return KeePassXCCredential{}, err
			}
			return credential, nil
		}
	}
	return KeePassXCCredential{}, fmt.Errorf("KeePassXC entry %q not found in %s", title, dbPath)
}

func validateKeePassXCCredential(title string, credential KeePassXCCredential) error {
	if credential.Username == "" || credential.Password == "" {
		return fmt.Errorf("KeePassXC entry %q has empty username or password", title)
	}
	if credential.WalletLocation == "" {
		return fmt.Errorf("KeePassXC entry %q has empty Wallet_Location", title)
	}
	return nil
}

func resolveKeePassDBPath(dbFileName string) (string, error) {
	candidates := keepassDBPathCandidates(dbFileName)
	for _, candidate := range candidates {
		if candidate == "" {
			continue
		}
		if info, err := os.Stat(candidate); err == nil && !info.IsDir() {
			abs, absErr := filepath.Abs(candidate)
			if absErr == nil {
				return abs, nil
			}
			return candidate, nil
		}
	}
	return "", fmt.Errorf("KeePassXC database file not found: %s", dbFileName)
}

func keepassDBPathCandidates(dbFileName string) []string {
	dbFileName = filepath.Clean(dbFileName)
	base := filepath.Base(dbFileName)
	altBase := base
	if strings.EqualFold(filepath.Ext(base), ".dbx") {
		altBase = strings.TrimSuffix(base, filepath.Ext(base)) + ".kdbx"
	}
	candidates := []string{dbFileName}
	if altBase != base {
		candidates = append(candidates, filepath.Join(filepath.Dir(dbFileName), altBase))
	}
	if !filepath.IsAbs(dbFileName) {
		if exePath, err := os.Executable(); err == nil {
			exeDir := filepath.Dir(exePath)
			candidates = append(candidates, filepath.Join(exeDir, dbFileName))
			if altBase != base {
				candidates = append(candidates, filepath.Join(exeDir, altBase))
			}
		}
		demoDir := filepath.Join("examples", "compiler_v1", "43_crypto_ffi_demo", "App")
		candidates = append(candidates, filepath.Join(demoDir, base))
		if altBase != base {
			candidates = append(candidates, filepath.Join(demoDir, altBase))
		}
	}
	return candidates
}

func readKeePassManagerProfileForKeyring(keyringName string, dbPath string) (keepassProfile, error) {
	candidates := []string{keyringName}
	if !strings.EqualFold(keyringName, strings.TrimSuffix(keyringName, filepath.Ext(keyringName))) {
		candidates = append(candidates, strings.TrimSuffix(keyringName, filepath.Ext(keyringName)))
	}
	baseName := filepath.Base(dbPath)
	candidates = append(candidates, baseName, strings.TrimSuffix(baseName, filepath.Ext(baseName)), dbPath)
	seen := map[string]bool{}
	var lastErr error
	for _, candidate := range candidates {
		candidate = strings.TrimSpace(candidate)
		if candidate == "" || seen[strings.ToLower(candidate)] {
			continue
		}
		seen[strings.ToLower(candidate)] = true
		profile, err := readKeePassManagerProfile(candidate)
		if err == nil {
			return profile, nil
		}
		lastErr = err
	}
	if lastErr != nil {
		return keepassProfile{}, lastErr
	}
	return keepassProfile{}, fmt.Errorf("no KeePass Manager credentials found for keyring/profile %q", keyringName)
}

func readKeePassManagerProfile(dbName string) (keepassProfile, error) {
	profileKeys := []string{
		"Profile_" + dbName,
	}
	baseName := filepath.Base(dbName)
	if baseName != dbName {
		profileKeys = append(profileKeys, "Profile_"+baseName)
	}
	var lastErr error
	for _, profileKey := range profileKeys {
		for _, target := range keepassManagerCredentialTargets(profileKey) {
			profileJSON, err := readWindowsCredentialText(target)
			if err != nil {
				lastErr = err
				continue
			}
			var profile keepassProfile
			if err := json.Unmarshal([]byte(profileJSON), &profile); err != nil {
				return keepassProfile{}, fmt.Errorf("parse KeePass Manager profile %q: %w", profileKey, err)
			}
			if profile.Password == "" {
				return keepassProfile{}, fmt.Errorf("KeePass Manager profile %q has no password field", profileKey)
			}
			profile.KeyPath = strings.TrimSpace(profile.KeyPath)
			return profile, nil
		}
	}
	if lastErr != nil {
		return keepassProfile{}, fmt.Errorf("no KeePass Manager credentials found for database %q; please log in via KeePass Manager UI first", dbName)
	}
	return keepassProfile{}, fmt.Errorf("no KeePass Manager credentials found for database %q; please log in via KeePass Manager UI first", dbName)
}

func keepassManagerCredentialTargets(profileKey string) []string {
	return []string{
		profileKey + "@" + keepassManagerService,
		keepassManagerService + "/" + profileKey,
		keepassManagerService + ":" + profileKey,
		profileKey,
	}
}

func keepassxcListPaths(dbName string, profile keepassProfile) ([]string, error) {
	args := keepassxcDBArgs([]string{"ls", "--quiet", "--recursive", "--flatten"}, dbName, profile, "/")
	output, err := keepassxcRunWithPassword(args, profile.Password)
	if err != nil {
		return nil, fmt.Errorf("keepassxc-cli ls: %w: %s", err, strings.TrimSpace(output))
	}
	lines := strings.Split(output, "\n")
	paths := make([]string, 0, len(lines))
	for _, line := range lines {
		entryPath := strings.TrimSpace(line)
		if entryPath == "" || entryPath == "/" {
			continue
		}
		paths = append(paths, entryPath)
	}
	return paths, nil
}

func keepassxcShowEntry(dbName string, entryPath string, profile keepassProfile) (keepassEntryRow, error) {
	args := keepassxcDBArgs([]string{
		"show",
		"--quiet",
		"--attributes", "Title",
		"--attributes", "UserName",
		"--attributes", "Notes",
	}, dbName, profile, entryPath)
	output, err := keepassxcRunWithPassword(args, profile.Password)
	if err != nil {
		return keepassEntryRow{}, err
	}
	lines := strings.Split(strings.ReplaceAll(output, "\r\n", "\n"), "\n")
	row := keepassEntryRow{Title: filepath.Base(entryPath), Username: "-", Notes: "-"}
	if len(lines) > 0 && strings.TrimSpace(lines[0]) != "" {
		row.Title = strings.TrimSpace(lines[0])
	}
	if len(lines) > 1 && strings.TrimSpace(lines[1]) != "" {
		row.Username = strings.TrimSpace(lines[1])
	}
	if len(lines) > 2 && strings.TrimSpace(lines[2]) != "" {
		row.Notes = strings.TrimSpace(strings.Join(lines[2:], " / "))
	}
	return row, nil
}

func keepassxcShowCredential(dbName string, entryPath string, profile keepassProfile) (KeePassXCCredential, error) {
	credential, err := keepassxcShowCredentialAll(dbName, entryPath, profile)
	if err == nil {
		return credential, nil
	}

	args := keepassxcDBArgs([]string{
		"show",
		"--quiet",
		"--show-protected",
		"--attributes", "UserName",
		"--attributes", "Password",
	}, dbName, profile, entryPath)
	var output string
	output, err = keepassxcRunWithPassword(args, profile.Password)
	if err != nil {
		return KeePassXCCredential{}, fmt.Errorf("%w: %s", err, strings.TrimSpace(output))
	}
	lines := strings.Split(strings.ReplaceAll(output, "\r\n", "\n"), "\n")
	credential = KeePassXCCredential{}
	if len(lines) > 0 {
		credential.Username = strings.TrimSpace(lines[0])
	}
	if len(lines) > 1 {
		credential.Password = strings.TrimSpace(lines[1])
	}
	return credential, nil
}

func keepassxcShowCredentialAll(dbName string, entryPath string, profile keepassProfile) (KeePassXCCredential, error) {
	args := keepassxcDBArgs([]string{
		"show",
		"--quiet",
		"--show-protected",
		"--all",
	}, dbName, profile, entryPath)
	output, err := keepassxcRunWithPassword(args, profile.Password)
	if err != nil {
		return KeePassXCCredential{}, fmt.Errorf("%w: %s", err, strings.TrimSpace(output))
	}
	return parseKeePassCredentialAttributes(output), nil
}

func parseKeePassCredentialAttributes(output string) KeePassXCCredential {
	credential := KeePassXCCredential{}
	for _, line := range strings.Split(strings.ReplaceAll(output, "\r\n", "\n"), "\n") {
		key, value, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		value = strings.TrimSpace(value)
		switch strings.ToLower(strings.ReplaceAll(key, " ", "_")) {
		case "username", "user_name":
			credential.Username = value
		case "password":
			credential.Password = value
		case "wallet_location", "walletlocation":
			credential.WalletLocation = normalizeWalletLocation(value)
		case "tags":
			if credential.WalletLocation == "" {
				credential.WalletLocation = walletLocationFromTags(value)
			}
		}
	}
	return credential
}

func normalizeWalletLocation(text string) string {
	text = strings.TrimSpace(text)
	if text == "" {
		return ""
	}
	for _, prefix := range []string{"Wallet_Location=", "Wallet_Location:", "Wallet Location=", "Wallet Location:"} {
		if strings.HasPrefix(strings.ToLower(text), strings.ToLower(prefix)) {
			return strings.TrimSpace(text[len(prefix):])
		}
	}
	return text
}

func walletLocationFromTags(tags string) string {
	tags = strings.ReplaceAll(tags, "\r\n", ",")
	tags = strings.ReplaceAll(tags, "\n", ",")
	tags = strings.ReplaceAll(tags, ";", ",")
	for _, tag := range strings.Split(tags, ",") {
		location := normalizeWalletLocation(tag)
		if location != "" && !strings.EqualFold(strings.TrimSpace(tag), strings.TrimSpace(location)) {
			return location
		}
	}
	return ""
}

func keepassxcDBArgs(prefix []string, dbName string, profile keepassProfile, tail string) []string {
	args := append([]string{}, prefix...)
	if profile.KeyPath != "" {
		args = append(args, "--key-file", profile.KeyPath)
	}
	args = append(args, dbName)
	if tail != "" {
		args = append(args, tail)
	}
	return args
}

func keepassxcRunWithPassword(args []string, password string) (string, error) {
	cmd := exec.Command("keepassxc-cli", args...)
	cmd.Stdin = strings.NewReader(password + "\n")
	output, err := cmd.CombinedOutput()
	return string(output), err
}

func formatKeePassRows(dbName string, rows []keepassEntryRow) string {
	var out strings.Builder
	out.WriteString("Entries in ")
	out.WriteString(dbName)
	out.WriteString("\n")
	out.WriteString(strings.Repeat("-", 100))
	out.WriteString("\n")
	out.WriteString(fmt.Sprintf("%-30s | %-32s | %s\n", "TITLE (Target Name)", "USERNAME", "COMMENT"))
	out.WriteString(strings.Repeat("-", 100))
	out.WriteString("\n")
	for _, row := range rows {
		out.WriteString(fmt.Sprintf("%-30s | %-32s | %s\n", truncateCell(row.Title, 30), truncateCell(row.Username, 32), truncateCell(singleLine(row.Notes), 50)))
	}
	out.WriteString(strings.Repeat("-", 100))
	out.WriteString("\n")
	out.WriteString(fmt.Sprintf("Total entries: %d", len(rows)))
	return out.String()
}

func truncateCell(text string, maxLen int) string {
	if text == "" {
		return "-"
	}
	runes := []rune(text)
	if len(runes) <= maxLen {
		return text
	}
	if maxLen <= 3 {
		return string(runes[:maxLen])
	}
	return string(runes[:maxLen-3]) + "..."
}

func singleLine(text string) string {
	text = strings.TrimSpace(text)
	text = strings.ReplaceAll(text, "\r\n", " / ")
	text = strings.ReplaceAll(text, "\n", " / ")
	text = strings.ReplaceAll(text, "\r", " / ")
	return text
}

func readWindowsCredentialText(target string) (string, error) {
	credential, err := readWindowsCredential(target)
	if err != nil {
		return "", err
	}
	if len(credential) == 0 {
		return "", fmt.Errorf("credential %q is empty", target)
	}
	return decodeCredentialBlob(credential), nil
}

func readWindowsCredential(target string) ([]byte, error) {
	targetName, err := syscall.UTF16PtrFromString(target)
	if err != nil {
		return nil, err
	}
	var credentialPtr uintptr
	result, _, callErr := procCredRead.Call(
		uintptr(unsafe.Pointer(targetName)),
		uintptr(credTypeGeneric),
		0,
		uintptr(unsafe.Pointer(&credentialPtr)),
	)
	if result == 0 {
		return nil, callErr
	}
	defer procCredFree.Call(credentialPtr)
	credential := (*windowsCredential)(unsafe.Pointer(credentialPtr))
	if credential.CredentialBlobSize == 0 || credential.CredentialBlob == nil {
		return nil, nil
	}
	blob := unsafe.Slice(credential.CredentialBlob, credential.CredentialBlobSize)
	copyBlob := make([]byte, len(blob))
	copy(copyBlob, blob)
	return copyBlob, nil
}

func decodeCredentialBlob(blob []byte) string {
	if len(blob)%2 == 0 {
		utf16Data := make([]uint16, len(blob)/2)
		for i := range utf16Data {
			utf16Data[i] = binary.LittleEndian.Uint16(blob[i*2:])
		}
		decoded := strings.TrimRight(string(utf16.Decode(utf16Data)), "\x00")
		if strings.Contains(decoded, "password") || strings.HasPrefix(strings.TrimSpace(decoded), "{") {
			return decoded
		}
	}
	return strings.TrimRight(string(blob), "\x00")
}

// KeyringHasKeePassXCMasterKey reports whether a namespaced KeePassXC master
// key exists in Windows Credential Manager.
func KeyringHasKeePassXCMasterKey(label string) (bool, error) {
	target, err := keyringTarget(label)
	if err != nil {
		return false, err
	}
	targetName, err := syscall.UTF16PtrFromString(target)
	if err != nil {
		return false, err
	}
	var credentialPtr uintptr
	result, _, callErr := procCredRead.Call(
		uintptr(unsafe.Pointer(targetName)),
		uintptr(credTypeGeneric),
		0,
		uintptr(unsafe.Pointer(&credentialPtr)),
	)
	if result == 0 {
		if isCredentialNotFound(callErr) {
			return false, nil
		}
		return false, fmt.Errorf("read KeePassXC master key metadata from Windows Credential Manager: %w", callErr)
	}
	procCredFree.Call(credentialPtr)
	return true, nil
}

func keyringTarget(label string) (string, error) {
	label = strings.TrimSpace(label)
	if label == "" {
		return "", fmt.Errorf("KeePassXC keyring label must not be empty")
	}
	if strings.ContainsAny(label, "\x00\r\n") {
		return "", fmt.Errorf("KeePassXC keyring label contains an invalid character")
	}
	if len(label) > 160 {
		return "", fmt.Errorf("KeePassXC keyring label too long")
	}
	return credentialTargetPrefix + label, nil
}

func isCredentialNotFound(err error) bool {
	errno, ok := err.(syscall.Errno)
	return ok && (errno == syscall.Errno(2) || errno == syscall.Errno(1168))
}
