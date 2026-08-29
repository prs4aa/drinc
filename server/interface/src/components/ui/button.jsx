import React from "react";
import { cn } from "../../lib/utils";

const buttonVariants = {
  default: "bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 shadow-sm border border-blue-500/20",
  destructive: "bg-red-600/90 text-white hover:bg-red-600 active:bg-red-700 shadow-sm border border-red-500/20",
  outline: "border border-border bg-surface hover:bg-surface-elevated text-slate-200 hover:text-white",
  secondary: "bg-surface-elevated text-slate-200 hover:bg-slate-800 border border-border/60",
  ghost: "hover:bg-surface-elevated text-slate-300 hover:text-white",
  success: "bg-emerald-600 text-white hover:bg-emerald-500 active:bg-emerald-700 shadow-sm border border-emerald-500/20",
};

const buttonSizes = {
  default: "h-9 px-4 py-2 text-sm",
  sm: "h-8 rounded-md px-3 text-xs",
  lg: "h-11 rounded-md px-8 text-base",
  icon: "h-9 w-9 p-0",
};

export const Button = React.forwardRef(
  ({ className, variant = "default", size = "default", disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap rounded-lg font-medium transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500 disabled:pointer-events-none disabled:opacity-50",
          buttonVariants[variant] || buttonVariants.default,
          buttonSizes[size] || buttonSizes.default,
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
