# 设计原则

> 设计 SSOT（Heiman Agent 哲学铁律）
> 所有新模块上线前必须满足这七条铁律，违反任何一条都会导致视觉系统崩塌。

---

## 视觉血脉（定位）

**Heiman Agent** = 专业智能家居监控面板 × 数据密度优先 × **海曼蓝作功能色（不作面色）**。

类比：**安防监控中心**——深色背板承载关键数据与告警，蓝色用于指示正常状态，红色用于告警。信息组织遵循 **数据密度 > 装饰** 的硬约束，任何不传递信息的视觉元素（渐变、阴影、装饰图案、立体透视）都被剔除。

---

## 七条铁律

### 1. 深色主线 + 海曼蓝作功能色

`#007AFF` 只用于 **link / active / CTA / focus**，**不允许大面积铺底**。

视觉口诀：**深面板 → 深画布 → 卡片**，层次靠深浅交替。

- 左 Sidebar：`bg-slate-800`（深蓝灰）
- 中间 chrome + canvas：TopBar / StatusRibbon / 主区都用 `bg-slate-900`（更深）
- 内容卡片：`<section>` 用 `bg-slate-800`（深蓝灰）浮在深 canvas 上
- panel 内的差异化元素：用 `bg-slate-700`（稍浅）或 `bg-slate-950`（更深，hover 态）

dark 主题已经是这个结构（canvas 暗 / 面板和卡片亮），与 light 主题对齐。

### 2. 状态用点不用块

**5px 圆点 + 5px 半透明光环** 替代色块 badge / chip。

色映射：`ok=success(绿)` / `info=info(蓝)` / `warn=warning(黄)` / `danger=error(红)` / `brand=brand-primary(海曼蓝)`。

chip 是给"可点击的预设/筛选"，**不是状态信号**——别混。

### 3. 数字字体强制走 mono

任何 **IID / device_id / token / 时间戳 / 计数 / 百分比 / 价格**，**必须**：

- 单数字 → `class="font-mono"`（强调 tabular-nums）
- 一段英文 ID → `class="font-mono"`（同 family，语义自解释）
- dev tool 风 caption（`now`、`42 events`、`status=normal`）→ `class="text-xs font-mono"`

### 4. 颜色自动生效

所有颜色走 Tailwind 语义类（`bg-slate-800` 这种）。**禁止 hex / rgb 内联**（资产级 logo 例外）。

### 5. 响应式断点只用 Tailwind 标配

`sm:` (640px) / `md:` (768px) / `lg:` (1024px) / `xl:` (1280px)。**禁止再发明 breakpoint**（诸如 900px、840px 这种）。

### 6. 动效克制

- hover 仅改 border 颜色 + 极小 transform（`scale(0.99)`）
- **不上 box-shadow 抬升**
- 过渡时长 ≤ 320ms

通用动画类：

- `class="transition-all duration-300"` — 通用过渡
- `class="hover:scale-99"` — 极克制 hover

### 7. 没有 emoji（代码注释除外）

正文用 Lucide React SVG（`src/components/icons.tsx`），**不要**直接把 `🏠`、`✨` 写进文案。

---

## "深 - 浅深 - 深" 三段式应用规则

| 区域 | 颜色 token | 备注 |
|------|-----------|------|
| 左 Sidebar | `bg-slate-800` | 应用左面板 |
| TopBar | `bg-slate-800` | 与左面板齐平 |
| StatusRibbon / 主 canvas | `bg-slate-900` | 工作区底色 |
| 内容卡片 `<section>` | `bg-slate-800` | 浮在深 canvas 上 |
| Modal / Drawer 内表面 | `bg-slate-800` | 同卡片 |
| chip / hover 态 / 输入框（在深面板内） | `bg-slate-700` 或 `bg-slate-950` | inset 视觉 |
| 传感器告警舞台 | `bg-red-950/50` | 与上述四档无关，独立强对比 |

---

## 修改设计 token 的决策权

LLM 默认**不允许**改 design token / 改铁律。改动流程：

1. **加 token**：先写到 `src/index.css`，然后回 `design-tokens.md` 加一行
2. **加组件原型**：先在某个页面落地一次，等被另一页复用时，再抽到 `component-patterns.md`
3. **改铁律（本文档）**：必须在 Tech RFC 留痕，人类负责拍板