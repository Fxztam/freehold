// Package oracleshim provides a primitive, FFI-friendly wrapper around the
// vendored go-ora Oracle driver. All exported functions use only string and
// (string, error) signatures so they can be bound directly from Freehold via
// the @ffi mechanism (String <-> string, Result<String, E> <-> (string, error)).
package oracleshim

import (
	"database/sql"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	// Registers the "oracle" driver with database/sql via its init().
	_ "github.com/sijms/go-ora/v2"
)

// walletDSN augments a base "oracle://user:pass@host:port/service" connection
// string with the TLS + wallet query parameters required to reach an Oracle
// Autonomous Database (Oracle Cloud) using a downloaded wallet folder. This
// mirrors the upstream go-ora hello_ora_wallet example:
//
//	connStr + "?SSL=enable&SSL Verify=false&WALLET=" + url.QueryEscape(walletPath)
//
// If the base string already carries query parameters the wallet parameters
// are appended with "&" instead of "?".
func walletDSN(connStr string, walletPath string) string {
	return walletDSNWithTimeout(connStr, walletPath, 0)
}

// walletDSNWithTimeout also sets go-ora's CONNECT TIMEOUT and TIMEOUT options
// in seconds when timeoutSeconds is greater than zero.
func walletDSNWithTimeout(connStr string, walletPath string, timeoutSeconds int64) string {
	separator := "?"
	if strings.Contains(connStr, "?") {
		separator = "&"
	}
	ret := connStr + separator + "SSL=enable&SSL Verify=false&WALLET=" + url.QueryEscape(walletPath)
	if timeoutSeconds > 0 {
		ret += "&CONNECT TIMEOUT=" + strconv.FormatInt(timeoutSeconds, 10)
		ret += "&TIMEOUT=" + strconv.FormatInt(timeoutSeconds, 10)
	}
	return ret
}

// ConnWithCredentials returns an oracle:// URL with username/password set in
// URL userinfo. connTarget may be a full oracle:// URL, a URL with placeholder
// credentials, or a host:port/service target without scheme.
func ConnWithCredentials(connTarget string, username string, password string) (string, error) {
	connTarget = strings.TrimSpace(connTarget)
	username = strings.TrimSpace(username)
	if connTarget == "" {
		return "", fmt.Errorf("Oracle connection target must not be empty")
	}
	if username == "" {
		return "", fmt.Errorf("Oracle username must not be empty")
	}
	if password == "" {
		return "", fmt.Errorf("Oracle password must not be empty")
	}
	if !strings.Contains(connTarget, "://") {
		return "oracle://" + url.UserPassword(username, password).String() + "@" + connTarget, nil
	}
	parsed, err := url.Parse(connTarget)
	if err != nil {
		return "", fmt.Errorf("parse Oracle connection target: %w", err)
	}
	if parsed.Scheme == "" {
		parsed.Scheme = "oracle"
	}
	if parsed.Host == "" {
		return "", fmt.Errorf("Oracle connection target has no host")
	}
	parsed.User = url.UserPassword(username, password)
	return parsed.String(), nil
}

// ConnFromWalletTNS reads tnsnames.ora from walletPath, extracts the first
// HOST/PORT/SERVICE_NAME triple, and returns an oracle:// connection URL with
// username/password set in URL userinfo.
func ConnFromWalletTNS(walletPath string, username string, password string) (string, error) {
	walletPath = strings.TrimSpace(walletPath)
	if walletPath == "" {
		return "", fmt.Errorf("Oracle wallet path must not be empty")
	}
	tnsPath := filepath.Join(walletPath, "tnsnames.ora")
	contentBytes, err := os.ReadFile(tnsPath)
	if err != nil {
		return "", fmt.Errorf("read %s: %w", tnsPath, err)
	}
	host, port, service, err := parseTNSConnectTarget(string(contentBytes))
	if err != nil {
		return "", fmt.Errorf("parse %s: %w", tnsPath, err)
	}
	return ConnWithCredentials(host+":"+port+"/"+service, username, password)
}

func parseTNSConnectTarget(content string) (string, string, string, error) {
	content = stripTNSComments(content)
	hosts := regexp.MustCompile(`(?is)\(\s*HOST\s*=\s*([^\)\s]+)`).FindAllStringSubmatch(content, -1)
	ports := regexp.MustCompile(`(?is)\(\s*PORT\s*=\s*([^\)\s]+)`).FindAllStringSubmatch(content, -1)
	services := regexp.MustCompile(`(?is)\(\s*SERVICE_NAME\s*=\s*([^\)\s]+)`).FindAllStringSubmatch(content, -1)
	if len(hosts) == 0 {
		return "", "", "", fmt.Errorf("no HOST entry found")
	}
	if len(ports) == 0 {
		return "", "", "", fmt.Errorf("no PORT entry found")
	}
	if len(services) == 0 {
		return "", "", "", fmt.Errorf("no SERVICE_NAME entry found")
	}
	return strings.TrimSpace(hosts[0][1]), strings.TrimSpace(ports[0][1]), strings.TrimSpace(services[0][1]), nil
}

func stripTNSComments(content string) string {
	lines := strings.Split(strings.ReplaceAll(content, "\r\n", "\n"), "\n")
	for i, line := range lines {
		if commentIndex := strings.Index(line, "#"); commentIndex >= 0 {
			lines[i] = line[:commentIndex]
		}
	}
	return strings.Join(lines, "\n")
}

// Ping opens a connection described by connStr and verifies it is reachable.
// It returns an empty string on success, or the error text on failure. This
// shape maps cleanly onto a Freehold routine returning a plain String.
func Ping(connStr string) string {
	db, err := sql.Open("oracle", connStr)
	if err != nil {
		return fmt.Sprintf("open oracle connection: %v", err)
	}
	defer db.Close()
	if err := db.Ping(); err != nil {
		return fmt.Sprintf("ping oracle database: %v", err)
	}
	return ""
}

// QueryScalar runs query against connStr and returns the first column of the
// first row rendered as a string. Maps onto Freehold Result<String, E>.
func QueryScalar(connStr string, query string) (string, error) {
	db, err := sql.Open("oracle", connStr)
	if err != nil {
		return "", fmt.Errorf("open oracle connection: %w", err)
	}
	defer db.Close()

	var value interface{}
	if err := db.QueryRow(query).Scan(&value); err != nil {
		return "", fmt.Errorf("query scalar %q: %w", query, err)
	}
	return fmt.Sprintf("%v", value), nil
}

// QueryRows runs query against connStr and returns a tab-separated table with
// a header row. maxRows limits the number of data rows when greater than zero.
// This keeps result sets FFI-friendly until Freehold has a richer row cursor ABI.
func QueryRows(connStr string, query string, maxRows int64) (string, error) {
	db, err := sql.Open("oracle", connStr)
	if err != nil {
		return "", fmt.Errorf("open oracle connection: %w", err)
	}
	defer db.Close()

	rows, err := db.Query(query)
	if err != nil {
		return "", fmt.Errorf("query rows %q: %w", query, err)
	}
	defer rows.Close()

	columns, err := rows.Columns()
	if err != nil {
		return "", fmt.Errorf("read result columns: %w", err)
	}

	var out strings.Builder
	out.WriteString(strings.Join(columns, "\t"))

	values := make([]interface{}, len(columns))
	scanTargets := make([]interface{}, len(columns))
	for i := range values {
		scanTargets[i] = &values[i]
	}

	var rowCount int64
	for rows.Next() {
		if maxRows > 0 && rowCount >= maxRows {
			break
		}
		if err := rows.Scan(scanTargets...); err != nil {
			return "", fmt.Errorf("scan result row: %w", err)
		}
		out.WriteString("\n")
		for i, value := range values {
			if i > 0 {
				out.WriteString("\t")
			}
			out.WriteString(formatCell(value))
		}
		rowCount++
	}
	if err := rows.Err(); err != nil {
		return "", fmt.Errorf("iterate result rows: %w", err)
	}
	return out.String(), nil
}

func formatCell(value interface{}) string {
	if value == nil {
		return "NULL"
	}
	if bytes, ok := value.([]byte); ok {
		return string(bytes)
	}
	text := fmt.Sprintf("%v", value)
	text = strings.ReplaceAll(text, "\r", " ")
	text = strings.ReplaceAll(text, "\n", " ")
	text = strings.ReplaceAll(text, "\t", " ")
	return text
}

// QueryDemoRows reads the fixed FH_FFI_DEMO projection used by the Freehold
// Oracle demo into a fixed-size row array. The anonymous struct fields mirror
// the generated Freehold record fields for OracleDemoRow: Id, Name, Amount.
func QueryDemoRows(connStr string, query string) ([2]struct {
	Id     int64
	Name   string
	Amount int64
}, error) {
	var result [2]struct {
		Id     int64
		Name   string
		Amount int64
	}

	db, err := sql.Open("oracle", connStr)
	if err != nil {
		return result, fmt.Errorf("open oracle connection: %w", err)
	}
	defer db.Close()

	rows, err := db.Query(query)
	if err != nil {
		return result, fmt.Errorf("query demo rows %q: %w", query, err)
	}
	defer rows.Close()

	rowIndex := 0
	for rows.Next() {
		if rowIndex >= len(result) {
			break
		}
		var id interface{}
		var name interface{}
		var amount interface{}
		if err := rows.Scan(&id, &name, &amount); err != nil {
			return result, fmt.Errorf("scan demo row: %w", err)
		}
		idValue, err := int64Cell(id)
		if err != nil {
			return result, fmt.Errorf("convert demo row id: %w", err)
		}
		amountValue, err := int64Cell(amount)
		if err != nil {
			return result, fmt.Errorf("convert demo row amount: %w", err)
		}
		result[rowIndex].Id = idValue
		result[rowIndex].Name = formatCell(name)
		result[rowIndex].Amount = amountValue
		rowIndex++
	}
	if err := rows.Err(); err != nil {
		return result, fmt.Errorf("iterate demo rows: %w", err)
	}
	return result, nil
}

func int64Cell(value interface{}) (int64, error) {
	switch typed := value.(type) {
	case nil:
		return 0, fmt.Errorf("NULL is not an Integer")
	case int64:
		return typed, nil
	case int:
		return int64(typed), nil
	case int32:
		return int64(typed), nil
	case float64:
		return int64(typed), nil
	case float32:
		return int64(typed), nil
	case []byte:
		return strconv.ParseInt(string(typed), 10, 64)
	case string:
		return strconv.ParseInt(typed, 10, 64)
	default:
		return strconv.ParseInt(fmt.Sprintf("%v", typed), 10, 64)
	}
}

// Exec runs a non-query statement against connStr and returns the number of
// affected rows as a string. Maps onto Freehold Result<String, E>.
func Exec(connStr string, statement string) (string, error) {
	db, err := sql.Open("oracle", connStr)
	if err != nil {
		return "", fmt.Errorf("open oracle connection: %w", err)
	}
	defer db.Close()

	result, err := db.Exec(statement)
	if err != nil {
		return "", fmt.Errorf("exec statement: %w", err)
	}
	affected, err := result.RowsAffected()
	if err != nil {
		return "", fmt.Errorf("read rows affected: %w", err)
	}
	return strconv.FormatInt(affected, 10), nil
}

// PingWallet verifies a wallet-secured connection to an Oracle Autonomous
// Database. connStr is the base "oracle://user:pass@host:port/service" URL and
// walletPath points to the unzipped Oracle Wallet folder (containing
// ewallet.p12 / cwallet.sso). Returns "" on success or the error text.
func PingWallet(connStr string, walletPath string) string {
	return Ping(walletDSN(connStr, walletPath))
}

// PingWalletTimeout is PingWallet with CONNECT TIMEOUT and TIMEOUT in seconds.
func PingWalletTimeout(connStr string, walletPath string, timeoutSeconds int64) string {
	return Ping(walletDSNWithTimeout(connStr, walletPath, timeoutSeconds))
}

// QueryScalarWallet runs a scalar query over a wallet-secured Autonomous
// Database connection. Maps onto Freehold Result<String, E>.
func QueryScalarWallet(connStr string, walletPath string, query string) (string, error) {
	return QueryScalar(walletDSN(connStr, walletPath), query)
}

// QueryScalarWalletTimeout is QueryScalarWallet with CONNECT TIMEOUT and
// TIMEOUT in seconds. Returned errors include the failed operation context.
func QueryScalarWalletTimeout(connStr string, walletPath string, query string, timeoutSeconds int64) (string, error) {
	return QueryScalar(walletDSNWithTimeout(connStr, walletPath, timeoutSeconds), query)
}

// QueryRowsWallet runs a row query over a wallet-secured Autonomous Database
// connection and returns a tab-separated table string.
func QueryRowsWallet(connStr string, walletPath string, query string, maxRows int64) (string, error) {
	return QueryRows(walletDSN(connStr, walletPath), query, maxRows)
}

// QueryRowsWalletTimeout is QueryRowsWallet with CONNECT TIMEOUT and TIMEOUT
// in seconds.
func QueryRowsWalletTimeout(connStr string, walletPath string, query string, maxRows int64, timeoutSeconds int64) (string, error) {
	return QueryRows(walletDSNWithTimeout(connStr, walletPath, timeoutSeconds), query, maxRows)
}

// QueryDemoRowsWalletTimeout returns the fixed FH_FFI_DEMO projection as typed
// rows for Freehold Array<Record,2> iteration.
func QueryDemoRowsWalletTimeout(connStr string, walletPath string, query string, timeoutSeconds int64) ([2]struct {
	Id     int64
	Name   string
	Amount int64
}, error) {
	return QueryDemoRows(walletDSNWithTimeout(connStr, walletPath, timeoutSeconds), query)
}

// ExecWallet runs a non-query statement over a wallet-secured Autonomous
// Database connection. Maps onto Freehold Result<String, E>.
func ExecWallet(connStr string, walletPath string, statement string) (string, error) {
	return Exec(walletDSN(connStr, walletPath), statement)
}

// ExecWalletTimeout is ExecWallet with CONNECT TIMEOUT and TIMEOUT in seconds.
func ExecWalletTimeout(connStr string, walletPath string, statement string, timeoutSeconds int64) (string, error) {
	return Exec(walletDSNWithTimeout(connStr, walletPath, timeoutSeconds), statement)
}
