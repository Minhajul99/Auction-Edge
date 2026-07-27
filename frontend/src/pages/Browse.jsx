import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { listAuctions } from "../services/api";
import { CATEGORIES } from "../constants";

const ENDING_SOON_WINDOW_MS = 3 * 24 * 60 * 60 * 1000; // 3 days
const PAGE_SIZE = 24;

const SORT_OPTIONS = [
  { value: "newest", label: "Newest" },
  { value: "ending_soonest", label: "Ending soonest" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
];

function sortAuctions(auctions, sortBy) {
  const sorted = [...auctions];
  switch (sortBy) {
    case "ending_soonest":
      return sorted.sort((a, b) => new Date(a.end_time) - new Date(b.end_time));
    case "price_asc":
      return sorted.sort((a, b) => Number(a.current_price) - Number(b.current_price));
    case "price_desc":
      return sorted.sort((a, b) => Number(b.current_price) - Number(a.current_price));
    default:
      return sorted;
  }
}

function PlaceholderImage() {
  return (
    <div className="flex h-full w-full items-center justify-center text-gray-300 dark:text-gray-600">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-12 w-12">
        <path fillRule="evenodd" d="M1.5 6A2.25 2.25 0 013.75 3.75h16.5A2.25 2.25 0 0122.5 6v12a2.25 2.25 0 01-2.25 2.25H3.75A2.25 2.25 0 011.5 18V6zM3 16.06V18c0 .414.336.75.75.75h16.5A.75.75 0 0021 18v-1.94l-2.69-2.689a1.5 1.5 0 00-2.12 0l-.88.879.97.97a.75.75 0 11-1.06 1.06l-5.16-5.159a1.5 1.5 0 00-2.12 0L3 16.061zm10.125-7.81a1.125 1.125 0 112.25 0 1.125 1.125 0 01-2.25 0z" clipRule="evenodd" />
      </svg>
    </div>
  );
}

function AuctionCard({ auction }) {
  return (
    <Link
      to={`/auctions/${auction.id}`}
      className="group flex flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-lg dark:border-white/10 dark:bg-gray-900"
    >
      <div className="relative aspect-4/3 w-full overflow-hidden bg-gray-100 dark:bg-gray-800">
        {auction.photo ? (
          <img
            src={auction.photo}
            alt=""
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <PlaceholderImage />
        )}
        {auction.reserve_met && (
          <span className="absolute left-2 top-2 rounded-full bg-emerald-500/95 px-2 py-0.5 text-xs font-semibold text-white shadow-sm">
            Reserve met
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-1 p-4">
        <div className="truncate font-medium text-gray-900 dark:text-white" title={auction.title}>
          {auction.title}
        </div>
        <div className="text-lg font-semibold text-brand-600 dark:text-brand-400">
          ${auction.current_price}
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Ends {new Date(auction.end_time).toLocaleString()}
        </div>
      </div>
    </Link>
  );
}

function CardSkeleton() {
  return (
    <div className="animate-pulse overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/10 dark:bg-gray-900">
      <div className="aspect-4/3 w-full bg-gray-200 dark:bg-gray-800" />
      <div className="space-y-2 p-4">
        <div className="h-4 w-3/4 rounded bg-gray-200 dark:bg-gray-800" />
        <div className="h-4 w-1/2 rounded bg-gray-200 dark:bg-gray-800" />
        <div className="h-3 w-2/3 rounded bg-gray-200 dark:bg-gray-800" />
      </div>
    </div>
  );
}

function ScrollButton({ direction, onClick }) {
  const isLeft = direction === "left";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={isLeft ? "Scroll left" : "Scroll right"}
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-gray-300 bg-white text-gray-600 shadow-sm transition-colors hover:bg-gray-100 dark:border-white/15 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-white/10"
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
        {isLeft ? (
          <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clipRule="evenodd" />
        ) : (
          <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
        )}
      </svg>
    </button>
  );
}

function EndingSoonCarousel({ auctions }) {
  const scrollerRef = useRef(null);

  const endingSoon = useMemo(() => {
    const now = Date.now();
    return auctions
      .filter((a) => new Date(a.end_time).getTime() - now <= ENDING_SOON_WINDOW_MS)
      .sort((a, b) => new Date(a.end_time) - new Date(b.end_time));
  }, [auctions]);

  if (endingSoon.length === 0) return null;

  function scroll(direction) {
    scrollerRef.current?.scrollBy({ left: direction * 280, behavior: "smooth" });
  }

  return (
    <div className="mb-10">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-gray-900 dark:text-white">
            Ending Soon
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Closing within the next 3 days — don't miss out.
          </p>
        </div>
        <div className="hidden gap-2 sm:flex">
          <ScrollButton direction="left" onClick={() => scroll(-1)} />
          <ScrollButton direction="right" onClick={() => scroll(1)} />
        </div>
      </div>

      <div
        ref={scrollerRef}
        className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {endingSoon.map((a) => (
          <div key={a.id} className="w-56 shrink-0 snap-start">
            <AuctionCard auction={a} />
          </div>
        ))}
      </div>
    </div>
  );
}

function CategoryFilter({ selected, onSelect }) {
  const options = ["All", ...CATEGORIES];
  return (
    <div className="mb-6 flex flex-wrap gap-2">
      {options.map((c) => {
        const isActive = (c === "All" && !selected) || c === selected;
        return (
          <button
            key={c}
            type="button"
            onClick={() => onSelect(c === "All" ? null : c)}
            className={[
              "rounded-full px-3 py-1.5 text-sm font-medium transition-colors",
              isActive
                ? "bg-brand-500 text-white shadow-sm"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-white/10 dark:text-gray-300 dark:hover:bg-white/20",
            ].join(" ")}
          >
            {c}
          </button>
        );
      })}
    </div>
  );
}

function SearchAndFilters({ search, onSearch, sortBy, onSort, minPrice, maxPrice, onMinPrice, onMaxPrice }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="relative w-full sm:max-w-xs">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
        >
          <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
        </svg>
        <input
          type="text"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Search listings..."
          className="w-full rounded-md border border-gray-300 bg-white py-2 pl-9 pr-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/15 dark:bg-gray-900 dark:text-white"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-gray-400">$</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={minPrice}
            onChange={(e) => onMinPrice(e.target.value)}
            placeholder="Min"
            className="w-20 rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/15 dark:bg-gray-900 dark:text-white"
          />
          <span className="text-gray-400">–</span>
          <span className="text-gray-400">$</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={maxPrice}
            onChange={(e) => onMaxPrice(e.target.value)}
            placeholder="Max"
            className="w-20 rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/15 dark:bg-gray-900 dark:text-white"
          />
        </div>

        <select
          value={sortBy}
          onChange={(e) => onSort(e.target.value)}
          className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/15 dark:bg-gray-900 dark:text-white"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              Sort: {o.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export default function Browse() {
  const [auctions, setAuctions] = useState([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [category, setCategory] = useState(null);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");

  // Price filters are server-side and re-fetch on every keystroke, so
  // debounce them to avoid hammering the API while the user is still typing.
  const [debouncedMinPrice, setDebouncedMinPrice] = useState("");
  const [debouncedMaxPrice, setDebouncedMaxPrice] = useState("");
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedMinPrice(minPrice);
      setDebouncedMaxPrice(maxPrice);
    }, 400);
    return () => clearTimeout(t);
  }, [minPrice, maxPrice]);

  useEffect(() => {
    setLoading(true);
    setPage(1);
    listAuctions("Active", category, {
      minPrice: debouncedMinPrice,
      maxPrice: debouncedMaxPrice,
      page: 1,
      pageSize: PAGE_SIZE,
    })
      .then((results) => {
        setAuctions(results);
        setHasMore(results.length === PAGE_SIZE);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [category, debouncedMinPrice, debouncedMaxPrice]);

  function loadMore() {
    const nextPage = page + 1;
    setLoadingMore(true);
    listAuctions("Active", category, {
      minPrice: debouncedMinPrice,
      maxPrice: debouncedMaxPrice,
      page: nextPage,
      pageSize: PAGE_SIZE,
    })
      .then((results) => {
        setAuctions((prev) => [...prev, ...results]);
        setHasMore(results.length === PAGE_SIZE);
        setPage(nextPage);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingMore(false));
  }

  const visibleAuctions = useMemo(() => {
    const filtered = search.trim()
      ? auctions.filter((a) => a.title.toLowerCase().includes(search.trim().toLowerCase()))
      : auctions;
    return sortAuctions(filtered, sortBy);
  }, [auctions, search, sortBy]);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
          Live Auctions
        </h1>
        <p className="mt-1 text-gray-500 dark:text-gray-400">
          Bid on items closing soon — prices update in real time.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
          {error}
        </div>
      )}

      {!loading && <EndingSoonCarousel auctions={auctions} />}

      <CategoryFilter selected={category} onSelect={setCategory} />

      <SearchAndFilters
        search={search}
        onSearch={setSearch}
        sortBy={sortBy}
        onSort={setSortBy}
        minPrice={minPrice}
        maxPrice={maxPrice}
        onMinPrice={setMinPrice}
        onMaxPrice={setMaxPrice}
      />

      {loading ? (
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      ) : visibleAuctions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 py-16 text-center text-gray-500 dark:border-white/15 dark:text-gray-400">
          {search.trim()
            ? `No active auctions match "${search.trim()}".`
            : category
              ? `No active auctions in ${category} right now.`
              : "No active auctions right now — check back soon."}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {visibleAuctions.map((a) => (
              <AuctionCard key={a.id} auction={a} />
            ))}
          </div>

          {hasMore && !search.trim() && (
            <div className="mt-8 flex justify-center">
              <button
                type="button"
                onClick={loadMore}
                disabled={loadingMore}
                className="rounded-md border border-gray-300 px-5 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/15 dark:text-gray-200 dark:hover:bg-white/10"
              >
                {loadingMore ? "Loading..." : "Load more"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
