// Package naming implements the archive naming convention shared with the
// statement renderer: <customer>/<yyyy>/<yyyy-mm>_<account>.pdf
package naming

import (
	"fmt"
	"regexp"
	"strings"
)

var (
	customerRe = regexp.MustCompile(`^C[0-9]{4,10}$`)
	accountRe  = regexp.MustCompile(`^[A-Z]{2}[0-9]{2}[A-Z0-9]{8,30}$`)
)

// StatementName builds the archive name for a monthly statement.
func StatementName(customer, account string, year, month int) (string, error) {
	if !customerRe.MatchString(customer) {
		return "", fmt.Errorf("naming: bad customer id %q", customer)
	}
	account = strings.ToUpper(strings.ReplaceAll(account, " ", ""))
	if !accountRe.MatchString(account) {
		return "", fmt.Errorf("naming: bad account %q", account)
	}
	if year < 2000 || year > 2999 || month < 1 || month > 12 {
		return "", fmt.Errorf("naming: bad period %d-%d", year, month)
	}
	return fmt.Sprintf("%s/%04d/%04d-%02d_%s.pdf", customer, year, year, month, account), nil
}

// DownloadFilename is the file name offered to the browser (Content-Disposition).
func DownloadFilename(name string) string {
	i := strings.LastIndex(name, "/")
	base := name[i+1:]
	return "statement_" + base
}
