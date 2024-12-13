#!/usr/bin/perl

use strict;
use warnings;
use IO::Socket;

my $sock = IO::Socket->new(
  Domain => AF_INET,
  Type => SOCK_STREAM,
  Proto => 'tcp',
  PeerAddr => $ARGV[0],
  PeerPort => $ARGV[1],
) or die "socket: $!";

use constant {
  PUMP_CLOSED => 0,
  PUMP_READING => 1,
  PUMP_WRITING => 2,
};
my $state_down = PUMP_READING;
my $state_up = PUMP_READING;
my $buf_down = '';
my $buf_up = '';

die "blocking: $!" unless defined STDIN->blocking(0);
die "blocking: $!" unless defined STDOUT->blocking(0);
die "blocking: $!" unless defined $sock->blocking(0);

my $rfd;
my $wfd;
while ($state_up || $state_down) {
	$rfd = '';
	$wfd = '';
	if ($state_down == PUMP_READING) {
		vec($rfd, fileno($sock), 1) = 1;
	} elsif ($state_down == PUMP_WRITING) {
		vec($wfd, fileno(STDOUT), 1) = 1;
	}
	if ($state_up == PUMP_READING) {
		vec($rfd, fileno(STDIN), 1) = 1;
	} elsif ($state_up == PUMP_WRITING) {
		vec($wfd, fileno($sock), 1) = 1;
	}

	select($rfd, $wfd, undef, undef) == -1 and die "select: $!";

	if ($state_down == PUMP_READING) {
		if (vec($rfd, fileno($sock), 1)) {
			my $n = sysread($sock, $buf_down, 16384);
			die "sysread: $!" unless defined $n;
			if ($n == 0) {
				close STDOUT or die "close :$!";
				$state_down = PUMP_CLOSED;
			} else {
				$state_down = PUMP_WRITING;
			}
		}
	} elsif ($state_down == PUMP_WRITING) {
		if (vec($wfd, fileno(STDOUT), 1)) {
			my $n = syswrite(STDOUT, $buf_down);
			die "syswrite: $!" unless defined $n;
			substr($buf_down, 0, $n) = '';
			$state_down = 1 unless length($buf_down);
		}
	}
	if ($state_up == PUMP_READING) {
		if (vec($rfd, fileno(STDIN), 1)) {
			my $n = sysread(STDIN, $buf_up, 16384);
			die "sysread: $!" unless defined $n;
			if ($n == 0) {
				$sock->shutdown(SHUT_WR) or die "shutdown: $!";
				$state_up = PUMP_CLOSED;
			} else {
				$state_up = PUMP_WRITING;
			}
		}
	} elsif ($state_up == PUMP_WRITING) {
		if (vec($wfd, fileno($sock), 1)) {
			my $n = syswrite($sock, $buf_up);
			die "syswrite: $!" unless defined $n;
			substr($buf_up, 0, $n) = '';
			$state_up = 1 unless length($buf_up);
		}
	}
}
