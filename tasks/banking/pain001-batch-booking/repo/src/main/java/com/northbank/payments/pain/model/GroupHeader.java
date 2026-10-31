package com.northbank.payments.pain.model;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Objects;

/** GrpHdr: message-level identification and totals. */
public final class GroupHeader {
    private final String messageId;
    private final LocalDateTime creationDateTime;
    private final int numberOfTransactions;
    private final BigDecimal controlSum;
    private final String initiatingPartyName;

    public GroupHeader(String messageId, LocalDateTime creationDateTime, int numberOfTransactions,
                       BigDecimal controlSum, String initiatingPartyName) {
        this.messageId = Objects.requireNonNull(messageId, "messageId");
        this.creationDateTime = creationDateTime;
        this.numberOfTransactions = numberOfTransactions;
        this.controlSum = controlSum;
        this.initiatingPartyName = initiatingPartyName;
    }

    public String getMessageId() { return messageId; }
    public LocalDateTime getCreationDateTime() { return creationDateTime; }
    public int getNumberOfTransactions() { return numberOfTransactions; }
    /** CtrlSum as stated in the file, or null if absent. */
    public BigDecimal getControlSum() { return controlSum; }
    public String getInitiatingPartyName() { return initiatingPartyName; }
}
