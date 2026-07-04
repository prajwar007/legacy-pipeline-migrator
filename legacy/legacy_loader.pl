#!/usr/bin/perl

use strict;
use warnings;
use Time::Piece;
use constant LARGE_DEBIT_THRESHOLD => 10000;

# Usage:
#   perl legacy_loader.pl transactions.txt
#
# Input format (pipe-delimited):
# account_id|txn_type|amount|date
#
# Example:
# ACC1001|CREDIT|1500.50|2026-07-01
# ACC1002|DEBIT|7500|2026-07-01

my $file = shift(@ARGV) // die "Usage: $0 <transaction_file>\n";

open(my $fh, '<', $file) or die "Cannot open $file: $!\n";

my %totals;
my %large_debits;
my $line_no = 0;
my $error_count = 0;

while (my $line = <$fh>) {
    $line =~ s/\r?\n?$//;
    $line_no++;

    next if $line =~ /^\s*$/;

    my @fields = split /\|/, $line, -1;
    unless (@fields == 4) {
        warn "Line $line_no: expected 4 fields, got " . scalar(@fields) . "\n";
        $error_count++;
        next;
    }

    my ($account_id, $txn_type, $amount, $date) = @fields;

    #------------------------------------------------------------
    # Legacy regex-based validation. Amounts are intentionally
    # positive because DEBIT/CREDIT carries the direction.
    #------------------------------------------------------------

    if ($account_id eq '' || $txn_type eq '' || $amount eq '' || $date eq '') {
        warn "Line $line_no: Missing fields\n";
        $error_count++;
        next;
    }

    unless ($account_id =~ /^[A-Za-z0-9_]+$/) {
        warn "Line $line_no: Invalid account_id\n";
        $error_count++;
        next;
    }

    unless ($txn_type =~ /^(CREDIT|DEBIT)$/) {
        warn "Line $line_no: Invalid txn_type\n";
        $error_count++;
        next;
    }

    unless ($amount =~ /^\d+(?:\.\d{1,2})?$/) {
        warn "Line $line_no: Invalid amount\n";
        $error_count++;
        next;
    }

    unless ($date =~ /^\d{4}-\d{2}-\d{2}$/) {
        warn "Line $line_no: Invalid date\n";
        $error_count++;
        next;
    }

    my $parsed_date = eval { Time::Piece->strptime($date, '%Y-%m-%d') };
    if ($@ || !$parsed_date || $parsed_date->ymd ne $date) {
        warn "Line $line_no: Invalid calendar date\n";
        $error_count++;
        next;
    }

    #------------------------------------------------------------
    # Legacy style accumulation
    # Demonstrates hash auto-vivification
    #------------------------------------------------------------
    $totals{$txn_type} += $amount;

    #------------------------------------------------------------
    # Intentional string -> number coercion
    # $amount is still a string here.
    # Perl automatically converts it during numeric comparison.
    #------------------------------------------------------------
    if ($txn_type eq 'DEBIT' && $amount > LARGE_DEBIT_THRESHOLD) {
        $large_debits{$account_id}++;
    }
}

close $fh;

print "\n";
print "Transaction Totals\n";
print "==================\n";

printf "%-12s %15s\n", "TYPE", "TOTAL";
printf "%-12s %15s\n", "------------", "---------------";

#------------------------------------------------------------
# Legacy sort keys %hash idiom
#------------------------------------------------------------
foreach my $type (sort keys %totals) {
    printf "%-12s %15.2f\n", $type, $totals{$type};
}

print "\n";
print "Large Debit Accounts (>10000)\n";
print "=============================\n";

printf "%-20s %10s\n", "ACCOUNT", "COUNT";
printf "%-20s %10s\n", "--------------------", "----------";

foreach my $acct (sort keys %large_debits) {
    printf "%-20s %10d\n",
        $acct,
        $large_debits{$acct};
}

if ($error_count > 0) {
    warn "$error_count malformed or invalid record(s) found\n";
    exit 1;
}

exit 0;
