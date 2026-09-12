import Image from "next/image";

/** Shared source-bracket / play mark; the adjacent wordmark names the link. */
export function BrandMark() {
  return (
    <Image
      src="/brand/citereel.svg"
      alt=""
      width={32}
      height={32}
      className="brand-mark"
      unoptimized
    />
  );
}
