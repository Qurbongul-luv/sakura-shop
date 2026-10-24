import React, { useState, useEffect } from 'react';
import {
  Gift,
  Copy,
  Check,
  Share2,
  Trophy,
  Users,
  Clock,
  Sparkles,
  ExternalLink,
  Flame,
  Award,
} from 'lucide-react';
import { MyContestStats, LeaderboardEntry, Contest } from '../types';
import { Translations } from '../i18n';
import { EmptyState } from '../components/EmptyState';
import { triggerPetalBurst } from '../components/PetalBurst';
import { haptic, openTelegramLink } from '../utils/telegram';

interface ContestPageProps {
  initData: string;
  t: Translations;
  onExploreProducts: () => void;
}

interface PlaceStyle {
  badge: string;
  border: string;
  label: string;
}

const PLACE_STYLES: PlaceStyle[] = [
  { badge: '🥇', border: 'border-amber-200/50', label: 'text-amber-600' },
  { badge: '🥈', border: 'border-slate-200/50', label: 'text-slate-500' },
  { badge: '🥉', border: 'border-amber-700/20', label: 'text-amber-700' },
];
const DEFAULT_PLACE_STYLE: PlaceStyle = { badge: '🏅', border: 'border-sakura-pink/30', label: 'text-sakura-rose' };

export const ContestPage: React.FC<ContestPageProps> = ({
  initData,
  t,
  onExploreProducts,
}) => {
  const [stats, setStats] = useState<MyContestStats | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [timeLeft, setTimeLeft] = useState<{ days: number; hours: number; minutes: number; seconds: number } | null>(null);

  useEffect(() => {
    fetchContestData();
  }, [initData]);

  const fetchContestData = async () => {
    setLoading(true);
    try {
      const headers: Record<string, string> = initData
        ? { 'X-Telegram-Init-Data': initData }
        : {};

      // 1. Fetch user stats + active contest
      const statsResp = await fetch('/api/contest/my-stats', { headers });
      if (statsResp.ok) {
        const statsData: MyContestStats = await statsResp.json();
        setStats(statsData);
      }

      // 2. Fetch leaderboard
      const boardResp = await fetch('/api/contest/leaderboard?limit=10');
      if (boardResp.ok) {
        const boardData: LeaderboardEntry[] = await boardResp.json();
        setLeaderboard(boardData);
      }
    } catch (e) {
      console.error('Error fetching contest data:', e);
    } finally {
      setLoading(false);
    }
  };

  // Live countdown timer calculation
  useEffect(() => {
    if (!stats?.contest?.ends_at) return;

    const calculateTime = () => {
      const target = new Date(stats.contest!.ends_at).getTime();
      const now = new Date().getTime();
      const diff = target - now;

      if (diff <= 0) {
        setTimeLeft({ days: 0, hours: 0, minutes: 0, seconds: 0 });
        return;
      }

      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);

      setTimeLeft({ days, hours, minutes, seconds });
    };

    calculateTime();
    const timer = setInterval(calculateTime, 1000);
    return () => clearInterval(timer);
  }, [stats?.contest?.ends_at]);

  const handleCopyLink = () => {
    if (!stats?.invite_link) return;
    navigator.clipboard.writeText(stats.invite_link);
    setCopied(true);
    haptic.notification('success');
    triggerPetalBurst(0.5, 0.4);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleShareLink = () => {
    if (!stats?.invite_link || !stats?.contest) return;
    haptic.impact('medium');
    const shareText = `🌸 Sakura shop do'konining go'zal konkursida qatnashing va ajoyib sovg'alarni yutib oling! ✨\n🎁 Sovg'alar: ${(stats.contest.prizes ?? [stats.contest.prize_1, stats.contest.prize_2]).join(', ')}\n\nQatnashish uchun: ${stats.invite_link}`;
    const url = `https://t.me/share/url?url=${encodeURIComponent(stats.invite_link)}&text=${encodeURIComponent(shareText)}`;
    openTelegramLink(url);
  };

  if (loading) {
    return (
      <div className="p-6 max-w-md mx-auto space-y-4">
        <div className="h-44 rounded-3xl bg-sakura-pink/20 animate-pulse" />
        <div className="h-28 rounded-3xl bg-sakura-pink/20 animate-pulse" />
        <div className="h-64 rounded-3xl bg-sakura-pink/20 animate-pulse" />
      </div>
    );
  }

  if (!stats?.has_active_contest || !stats.contest) {
    return (
      <div className="pb-28">
        <EmptyState
          title={t.noActiveContest}
          subtitle="Tez orada yangi qimmatbaho sovg'alar va kiyimlar bilan tanlov e'lon qilinadi 🌸"
          actionButton={{
            text: t.continueShopping,
            onClick: onExploreProducts,
          }}
        />
      </div>
    );
  }

  const contest = stats.contest;
  const prizes = contest.prizes?.length ? contest.prizes : [contest.prize_1, contest.prize_2, contest.prize_3];
  const rank = stats.rank;
  const score = stats.score;
  const nextRankScore = stats.next_rank_score;

  return (
    <div className="p-4 pb-32 max-w-md mx-auto space-y-4 animate-fade-in">
      {/* Contest Banner Card */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-sakura-blush via-white to-sakura-cream dark:from-sakura-darkcard dark:to-sakura-darkbg p-5 border border-sakura-pink/30 shadow-sakura">
        <div className="absolute -top-4 -right-4 text-7xl opacity-15 select-none">🌸</div>

        <div className="flex items-center gap-2 mb-2">
          <span className="p-2 rounded-2xl bg-sakura-rose/10 text-sakura-rose dark:text-sakura-pink">
            <Gift className="w-5 h-5" />
          </span>
          <div>
            <h1 className="text-base font-extrabold text-sakura-plum dark:text-white leading-tight">
              {t.contestTitle}
            </h1>
            <span className="text-[11px] text-sakura-rose font-bold uppercase tracking-wider">
              {t.contestPrizes}
            </span>
          </div>
        </div>

        {/* Prizes Cards */}
        <div className="mt-3 space-y-2">
          {prizes.map((prize, index) => {
            const style = PLACE_STYLES[index] ?? DEFAULT_PLACE_STYLE;
            return (
              <div
                key={index}
                className={`flex items-center gap-3 ${index === 0 ? 'p-3 bg-white/80' : 'p-2.5 bg-white/70'} rounded-2xl dark:bg-sakura-darkcardsoft backdrop-blur-sm border ${style.border} shadow-xs`}
              >
                <span className="text-2xl">{style.badge}</span>
                <div className="flex-1 min-w-0">
                  <span className={`text-[10px] font-extrabold ${style.label} block uppercase`}>
                    {index + 1}-o'rin
                  </span>
                  <p className="text-xs font-bold text-sakura-plum dark:text-white truncate">{prize}</p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Countdown Timer */}
        {timeLeft && (
          <div className="mt-4 pt-3 border-t border-sakura-pink/20">
            <div className="flex items-center justify-between text-xs text-sakura-plum/80 dark:text-sakura-blush/80 mb-1.5 font-bold">
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-sakura-rose" />
                <span>{t.timeRemaining}:</span>
              </span>
              <span className="text-sakura-rose font-mono text-[11px]">
                {contest.formatted_ends_at}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="p-1.5 rounded-xl bg-white/80 dark:bg-sakura-darkcardsoft border border-sakura-pink/20">
                <span className="block text-sm font-black text-sakura-plum dark:text-white">{timeLeft.days}</span>
                <span className="text-[9px] text-sakura-plum/60 dark:text-sakura-blush/60">kun</span>
              </div>
              <div className="p-1.5 rounded-xl bg-white/80 dark:bg-sakura-darkcardsoft border border-sakura-pink/20">
                <span className="block text-sm font-black text-sakura-plum dark:text-white">{timeLeft.hours}</span>
                <span className="text-[9px] text-sakura-plum/60 dark:text-sakura-blush/60">soat</span>
              </div>
              <div className="p-1.5 rounded-xl bg-white/80 dark:bg-sakura-darkcardsoft border border-sakura-pink/20">
                <span className="block text-sm font-black text-sakura-plum dark:text-white">{timeLeft.minutes}</span>
                <span className="text-[9px] text-sakura-plum/60 dark:text-sakura-blush/60">daq</span>
              </div>
              <div className="p-1.5 rounded-xl bg-white/80 dark:bg-sakura-darkcardsoft border border-sakura-pink/20">
                <span className="block text-sm font-black text-sakura-rose font-mono">{timeLeft.seconds}</span>
                <span className="text-[9px] text-sakura-plum/60 dark:text-sakura-blush/60">soniya</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Participant Personal Stats & Referral Link Card */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/30 shadow-sakura-sm space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xs text-sakura-plum/70 dark:text-sakura-blush/70 font-semibold">
              {t.myScore}
            </span>
            <div className="flex items-baseline gap-1 mt-0.5">
              <span className="text-2xl font-black text-sakura-rose dark:text-sakura-pink">
                {score}
              </span>
              <span className="text-xs text-sakura-plum/60 dark:text-sakura-blush/60">ta do'st</span>
            </div>
          </div>

          <div className="text-right">
            <span className="text-xs text-sakura-plum/70 dark:text-sakura-blush/70 font-semibold">
              {t.myRank}
            </span>
            <div className="mt-0.5">
              {rank ? (
                <span className="inline-flex items-center gap-1 px-3 py-0.5 rounded-full bg-sakura-blush dark:bg-sakura-darkcardsoft text-sakura-rose font-black text-sm">
                  <Award className="w-4 h-4" />
                  <span>#{rank}</span>
                </span>
              ) : (
                <span className="text-xs text-sakura-plum/50 italic">—</span>
              )}
            </div>
          </div>
        </div>

        {/* Motivational Rank Hint */}
        {rank && (
          <div className="p-2.5 rounded-2xl bg-sakura-cream dark:bg-sakura-darkcardsoft text-xs text-sakura-plum dark:text-sakura-blush font-medium flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-500 shrink-0" />
            <span>
              {rank === 1
                ? "Siz 1-o'rindasiz! Yetakchilikni saqlab qoling! 🌸"
                : nextRankScore !== null
                ? `Siz ${rank}-o'rindasiz, oldingi o'ringa ${nextRankScore} ball qoldi! 🌸`
                : `Siz ${rank}-o'rindasiz 🌸`}
            </span>
          </div>
        )}

        {/* Personal Invite Link */}
        <div className="pt-2">
          <label className="text-[11px] font-bold text-sakura-plum/80 dark:text-sakura-blush/80 block mb-1">
            {t.myLink}:
          </label>
          <div className="flex items-center gap-2 p-2 rounded-2xl bg-sakura-blush/50 dark:bg-sakura-darkbg border border-sakura-pink/30">
            <input
              type="text"
              readOnly
              value={stats.invite_link}
              className="bg-transparent text-xs font-mono text-sakura-plum dark:text-sakura-blush flex-1 outline-none select-all truncate"
            />
            <button
              onClick={handleCopyLink}
              className="p-1.5 rounded-xl bg-white dark:bg-sakura-darkcard text-sakura-rose shadow-xs active:scale-90 transition-transform"
              title="Copy"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="grid grid-cols-2 gap-2 pt-1">
          <button
            onClick={handleCopyLink}
            className="py-2.5 px-3 rounded-2xl bg-white dark:bg-sakura-darkcard text-sakura-rose font-bold text-xs flex items-center justify-center gap-1.5 border border-sakura-pink/30 active:scale-95 transition-transform shadow-xs"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? t.copied : t.copyLink}</span>
          </button>

          <button
            onClick={handleShareLink}
            className="py-2.5 px-3 rounded-2xl bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white font-extrabold text-xs flex items-center justify-center gap-1.5 shadow-sakura active:scale-95 transition-transform"
          >
            <Share2 className="w-3.5 h-3.5" />
            <span>{t.shareLink}</span>
          </button>
        </div>
      </div>

      {/* Top 10 Leaderboard */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/30 shadow-sakura-sm space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-extrabold text-sakura-plum dark:text-white flex items-center gap-1.5">
            <Trophy className="w-4 h-4 text-amber-500" />
            <span>{t.leaderboard}</span>
          </h2>
          <span className="text-[10px] text-sakura-rose font-bold uppercase tracking-wider">
            Top 10
          </span>
        </div>

        {leaderboard.length > 0 ? (
          <div className="space-y-1.5">
            {leaderboard.map((entry) => {
              const isMe = entry.user_id === stats.user_id;
              const medals: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' };
              const medal = medals[entry.rank];

              return (
                <div
                  key={entry.user_id}
                  className={`flex items-center justify-between p-2.5 rounded-2xl transition-all ${
                    isMe
                      ? 'bg-sakura-blush/90 dark:bg-sakura-darkcardsoft border border-sakura-rose/40 font-bold scale-[1.01]'
                      : 'bg-white/60 dark:bg-sakura-darkcardsoft/50 border border-sakura-pink/10'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="w-6 text-center font-extrabold text-xs">
                      {medal || <span className="text-sakura-plum/60 text-[11px]">#{entry.rank}</span>}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-sakura-plum dark:text-white truncate flex items-center gap-1">
                        <span>{entry.name}</span>
                        {isMe && (
                          <span className="px-1.5 py-0.2 rounded-full bg-sakura-rose text-white text-[9px] font-extrabold">
                            Siz
                          </span>
                        )}
                      </p>
                      {entry.username && (
                        <span className="text-[10px] text-sakura-plum/50 dark:text-sakura-blush/50 font-mono block">
                          @{entry.username}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="text-right shrink-0 pl-2">
                    <span className="text-xs font-black text-sakura-rose dark:text-sakura-pink">
                      {entry.score}
                    </span>
                    <span className="text-[10px] text-sakura-plum/60 dark:text-sakura-blush/60 ml-0.5">
                      ball
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-sakura-plum/60 italic text-center py-4">
            Hozircha hech kim ball to'plamadi. Birinchi bo'ling! 🌸
          </p>
        )}
      </div>

      {/* My Invites List */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/30 shadow-sakura-sm space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-extrabold text-sakura-plum dark:text-white flex items-center gap-1.5">
            <Users className="w-4 h-4 text-sakura-rose" />
            <span>{t.myInvites}</span>
          </h2>
          <span className="text-[10px] font-bold text-sakura-plum/60">
            Jami: {stats.invites.length}
          </span>
        </div>

        {stats.invites.length > 0 ? (
          <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
            {stats.invites.map((inv) => (
              <div
                key={inv.id}
                className="flex items-center justify-between p-2 rounded-2xl bg-sakura-cream/60 dark:bg-sakura-darkcardsoft/50 border border-sakura-pink/10 text-xs"
              >
                <div className="min-w-0 pr-2">
                  <p className="font-bold text-sakura-plum dark:text-white truncate">
                    {inv.name}
                  </p>
                  {inv.username && (
                    <span className="text-[10px] text-sakura-plum/50 font-mono">
                      @{inv.username}
                    </span>
                  )}
                </div>

                <div className="shrink-0">
                  {inv.status === 'confirmed' && (
                    <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 text-[10px] font-black">
                      <Check className="w-3 h-3" />
                      <span>{t.statusConfirmed}</span>
                    </span>
                  )}
                  {inv.status === 'pending' && (
                    <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 text-[10px] font-black">
                      <Clock className="w-3 h-3" />
                      <span>{t.statusPending}</span>
                    </span>
                  )}
                  {inv.status === 'revoked' && (
                    <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-rose-100 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 text-[10px] font-black">
                      <span>✕</span>
                      <span>{t.statusRevoked}</span>
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-sakura-plum/60 italic text-center py-3">
            Hozircha taklif qilingan do'stlar yo'q. Havolangizni ulashing! 🎀
          </p>
        )}
      </div>
    </div>
  );
};
