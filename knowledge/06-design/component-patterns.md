# 组件原型

> 设计 SSOT（Heiman Agent 组件原型）
> 写新模块时**直接复制粘贴这些原型**——它们已被锁进视觉契约，不要再发明新变体。

---

## 1. Card（业务最常用容器）

**默认形态**（自带 padding）：

```tsx
<section
  className="rounded-xl bg-slate-800 border border-slate-700 shadow-sm p-5 md:p-6"
  aria-labelledby="my-section-title"
>
  <div className="flex items-baseline justify-between gap-3 mb-4 flex-wrap">
    <h2
      id="my-section-title"
      className="text-lg font-semibold text-white inline-flex items-baseline gap-2"
    >
      标题
      <span className="text-xs font-mono text-slate-400 font-normal">
        slug_or_count
      </span>
    </h2>
  </div>
</section>
```

**列表型变体**（无内边距，把 padding 让给 row）：

```tsx
<section className="rounded-xl bg-slate-800 border border-slate-700 shadow-sm">
  <div className="flex items-baseline justify-between px-5 pt-4 pb-3">
    <h2 className="text-lg font-semibold text-white">...</h2>
  </div>
  <ul className="divide-y divide-slate-700">
    <li className="text-sm px-5 py-2.5 hover:bg-slate-700/50 transition-colors">
      ...
    </li>
  </ul>
</section>
```

---

## 2. Buttons

### 2.1 Primary CTA（主操作，每页 ≤1）

```tsx
<button
  type="button"
  className="text-sm px-5 py-2 rounded-md bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50 transition-colors"
>
  发送
</button>
```

### 2.2 Secondary（次操作，默认按钮）

```tsx
<button
  type="button"
  className="text-sm px-4 py-1.5 rounded-md bg-slate-700 text-slate-300 hover:text-white border border-slate-600 hover:border-slate-500 transition-colors"
>
  取消
</button>
```

### 2.3 Ghost（行内文字按钮）

```tsx
<button
  type="button"
  className="text-sm text-slate-400 hover:text-white transition-colors"
>
  跳转 →
</button>
```

### 2.4 Danger Solid（危险确认，二次）

```tsx
<button
  type="button"
  className="px-5 py-2 rounded-md bg-red-500 text-white hover:bg-red-600 transition-colors"
>
  删除
</button>
```

### 2.5 Soft Brand（被选中 / hover-active 反馈）

```tsx
<button className="px-3.5 py-1.5 rounded-md bg-blue-500/20 text-blue-400 hover:bg-blue-500 hover:text-white border border-transparent transition-colors">
  选中
</button>
```

### 2.6 Icon Button（icon-only，32×32 标准框）

```tsx
<button
  type="button"
  aria-label="刷新"
  className="w-8 h-8 inline-flex items-center justify-center rounded-md text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
>
  <RefreshCwIcon />
</button>
```

---

## 3. Status Dot（状态点 + 半透明光环）

**统一替代 chip / badge** 表达状态。规格：

- **5px 圆点**（`width:5; height:5`）+ `box-shadow: 0 0 0 3px var(--color-{tone}-bg)`
- 永远在 `inline-flex items-center gap-2` 容器内，后面跟 `<span>` 状态文字
- 颜色映射：`ok=green` / `info=blue` / `warn=yellow` / `danger=red` / `brand=blue`

```tsx
<span className="inline-flex items-center gap-2 text-xs text-slate-400">
  <span
    aria-hidden
    className="rounded-full bg-green-500"
    style={{
      width: 5,
      height: 5,
      boxShadow: "0 0 0 3px rgba(34, 197, 94, 0.2)",
    }}
  />
  在线
</span>
```

---

## 4. Drawer（右侧抽屉，设置 / 详情）

```tsx
<aside
  aria-label="设置"
  aria-modal="true"
  role="dialog"
  className={`fixed top-0 right-0 bottom-0 w-full md:w-[420px] max-w-md bg-slate-800 border-l border-slate-700 flex flex-col z-[60] transition-transform ${
    open ? "translate-x-0" : "translate-x-full"
  }`}
  style={{
    transitionDuration: "320ms",
    boxShadow: open ? "0 0 20px rgba(0,0,0,0.5)" : "none",
  }}
>
  <header
    className="flex items-center justify-between px-5 border-b border-slate-700"
    style={{ minHeight: 64 }}
  >
    <h2 className="text-lg font-semibold text-white">设置</h2>
    <CloseButton onClick={onClose} />
  </header>
  <div className="flex-1 overflow-y-auto px-5 py-4">{/* 内容 */}</div>
</aside>
```

所有 drawer 一律 **`max-w-md`**（448px）。

---

## 5. Dialog（居中弹窗）

```tsx
<div
  className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60"
  onClick={onClose}
>
  <div
    role="dialog"
    aria-modal="true"
    aria-labelledby="dialog-title"
    className="w-[90%] max-w-md bg-slate-800 border border-slate-700 rounded-2xl shadow-lg p-6"
    onClick={(e) => e.stopPropagation()}
  >
    <h2 id="dialog-title" className="text-lg font-semibold text-white mb-3">
      标题
    </h2>
    {/* 内容 */}
    <div className="mt-6 flex justify-end gap-2">
      <SecondaryButton onClick={onClose}>取消</SecondaryButton>
      <PrimaryButton onClick={onConfirm}>确定</PrimaryButton>
    </div>
  </div>
</div>
```

mobile bottom-sheet 变体：`items-end md:items-center` + `rounded-t-2xl md:rounded-2xl`。

---

## 6. Toast / Inline alert

调用方：

```ts
import { toast } from "@/components/Toast";
toast("已暂停", "ok" | "info" | "warn" | "danger");
```

inline 警告条（用于页面顶部，如错误提示）：

```tsx
<div className="text-sm rounded-lg bg-red-500/20 border border-red-500/30 text-red-400 px-4 py-2.5">
  <span className="font-medium">⚠ 错误</span>
  <span className="ml-2 text-red-400/80">描述信息</span>
</div>
```

---

## 7. Chip / Pill（标签 / 预设）

> ⚠️ 不要与 Status Dot 混淆 —— chip 用于**可点击的预设/筛选**，**不是状态信号**。

```tsx
<button className="text-xs px-2.5 py-1 rounded-full bg-slate-700 text-slate-300 hover:bg-blue-500/20 hover:text-blue-400 transition-colors">
  筛选条件
</button>
```

---

## 8. Source Tag（dev tool 风 mono 标签）

用于 ActivityFeed / 日志类列表，把 source 类型显式打出来：

```tsx
<span className="text-xs font-mono justify-self-start px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">
  sensor_log
</span>
```

色映射：

| source | 容器 | 文字 |
|--------|------|------|
| `sensor` | `bg-blue-500/20` | `text-blue-400` |
| `event` | `bg-slate-700` | `text-slate-300` |
| `alert` | `bg-red-500/20` | `text-red-400` |

---

## 9. Switch / Toggle（role=switch）

```tsx
<button
  type="button"
  role="switch"
  aria-checked={active}
  onClick={() => onToggle(!active)}
  className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none ${
    active ? "bg-blue-500" : "bg-slate-700 border border-slate-600"
  }`}
>
  <span
    className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
      active ? "translate-x-5" : "translate-x-0"
    }`}
  />
</button>
```

---

## 10. TabPanel:Loading / Error 占位

写在 main 容器内，与卡片共用 `rounded-xl bg-slate-800` 形态：

```tsx
<div
  className="rounded-xl bg-slate-800 border border-slate-700 shadow-sm p-12 text-center text-slate-400"
  role="status" aria-live="polite"
>
  <div className="inline-flex items-center gap-2">
    <span className="inline-block w-2 h-2 rounded-full bg-slate-500 animate-pulse" />
    正在加载数据…
  </div>
</div>

<div
  className="rounded-xl bg-slate-800 border border-red-500/50 shadow-sm p-8 text-center"
  role="alert"
>
  <div className="text-lg text-red-400 mb-3 font-normal">加载失败</div>
  <button
    type="button"
    onClick={onRetry}
    className="text-sm px-4 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-300 hover:text-white"
  >重试</button>
</div>
```