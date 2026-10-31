package com.meridian.ledger.reval;

import com.meridian.ledger.core.Account;
import com.meridian.ledger.core.AccountBalance;
import com.meridian.ledger.core.JournalEntry;
import com.meridian.ledger.core.Ledger;
import com.meridian.ledger.core.Posting;
import com.meridian.ledger.core.Side;
import com.meridian.ledger.fx.FxConverter;
import com.meridian.ledger.fx.RateTable;
import com.meridian.ledger.money.Money;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

/**
 * Month-end revaluation of foreign-currency monetary accounts (IAS 21.23).
 *
 * <p>For each open ASSET/LIABILITY account kept in a foreign currency, the carried
 * functional balance is brought to the account balance converted at the closing rate.
 * The difference is booked against the unrealised FX result account, one journal entry per
 * account revalued.
 */
public final class RevaluationService {
    private final Ledger ledger;
    private final Account fxResultAccount;

    public RevaluationService(Ledger ledger, Account fxResultAccount) {
        this.ledger = ledger;
        this.fxResultAccount = fxResultAccount;
        if (!fxResultAccount.getCurrency().equals(ledger.getFunctionalCurrency())) {
            throw new IllegalArgumentException("FX result account must be in functional currency");
        }
    }

    /** Posts the revaluation entries for {@code closingDate} and returns them in account order. */
    public List<JournalEntry> revalue(RateTable closingRates, LocalDate closingDate) {
        FxConverter converter = new FxConverter(closingRates);
        List<JournalEntry> posted = new ArrayList<>();
        int seq = 0;
        for (Account account : new ArrayList<>(ledger.accounts())) {
            if (!account.getType().isMonetary() || account.getCurrency().equals(ledger.getFunctionalCurrency())) {
                continue;
            }
            AccountBalance bal = ledger.balance(account);
            if (bal.getAmount().signum() == 0 && bal.getFunctional().signum() == 0) continue;

            Money target = converter.convert(Money.of(bal.getAmount(), account.getCurrency()), ledger.getFunctionalCurrency());
            BigDecimal delta = target.getAmount().subtract(bal.getFunctional());
            if (delta.signum() == 0) continue;

            Side accountSide = delta.signum() > 0 ? Side.DEBIT : Side.CREDIT;
            List<Posting> lines = new ArrayList<>();
            lines.add(new Posting(account, accountSide, Money.zero(account.getCurrency()), delta.abs()));
            lines.add(new Posting(fxResultAccount, accountSide.opposite(),
                    Money.of(delta.abs(), ledger.getFunctionalCurrency()), delta.abs()));
            JournalEntry e = new JournalEntry("REVAL-" + closingDate + "-" + (++seq), closingDate,
                    "FX revaluation " + account.getCode() + " at closing rate", lines);
            ledger.post(e);
            posted.add(e);
        }
        return posted;
    }
}
