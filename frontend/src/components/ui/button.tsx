import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none select-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-white hover:bg-primary-hover active:bg-[#163c9c]",
        secondary: "bg-surface text-ink border border-line-strong hover:bg-surface-2 hover:border-[#c4cedb]",
        ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink",
        subtle: "bg-primary-soft text-primary hover:bg-[#dce6fb]",
        danger: "bg-danger-base text-white hover:bg-danger",
        "danger-ghost": "text-danger hover:bg-danger-soft",
        link: "text-primary hover:underline underline-offset-4 px-0 h-auto",
      },
      size: {
        sm: "h-8 px-3 text-[13px] rounded-md [&_svg]:size-3.5",
        md: "h-9 px-4 text-[13.5px] rounded-md [&_svg]:size-4",
        lg: "h-11 px-5 text-[15px] rounded-lg [&_svg]:size-[18px]",
        icon: "size-9 rounded-md [&_svg]:size-[18px]",
        "icon-sm": "size-8 rounded-md [&_svg]:size-4",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button> & { asChild?: boolean; loading?: boolean };

export const Button = forwardRef<HTMLButtonElement, Props>(({ className, variant, size, asChild, loading, children, disabled, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp ref={ref} className={cn(button({ variant, size }), className)} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>
      {asChild ? children : (<>{loading && <Loader2 className="animate-spin" aria-hidden />}{children}</>)}
    </Comp>
  );
});
Button.displayName = "Button";
