from __future__ import annotations

"""PyQt 监控面板：展示每个 agent 的状态、动作和历史。"""

import queue
import sys
from typing import Any, Callable, Dict, Iterable, List

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class AgentCard(QGroupBox):
    def __init__(self, actor_id: str):
        super().__init__(f"智能体 | {actor_id}")
        self._actor_id = actor_id

        self._location = QLabel("-")
        self._hunger = QLabel("0")
        self._thirst = QLabel("0")
        self._fatigue = QLabel("0")
        self._step = QLabel("0")

        self._inventory = QPlainTextEdit()
        self._inventory.setReadOnly(True)
        self._inventory.setMaximumBlockCount(300)
        self._plan = QPlainTextEdit()
        self._plan.setReadOnly(True)
        self._plan.setMaximumBlockCount(300)
        self._action = QPlainTextEdit()
        self._action.setReadOnly(True)
        self._action.setMaximumBlockCount(120)
        self._reflect = QPlainTextEdit()
        self._reflect.setReadOnly(True)
        self._reflect.setMaximumBlockCount(200)
        self._memory = QPlainTextEdit()
        self._memory.setReadOnly(True)
        self._memory.setMaximumBlockCount(200)
        text_areas = [self._inventory, self._plan, self._action, self._reflect, self._memory]
        for text in text_areas:
            text.setMinimumHeight(160)
            text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        attrs_row = QWidget()
        attrs_layout = QHBoxLayout(attrs_row)
        attrs_layout.setContentsMargins(0, 0, 0, 0)
        attrs_layout.setSpacing(10)
        attrs_layout.addWidget(QLabel("饱食度"))
        attrs_layout.addWidget(self._hunger)
        attrs_layout.addWidget(QLabel("口渴度"))
        attrs_layout.addWidget(self._thirst)
        attrs_layout.addWidget(QLabel("疲劳度"))
        attrs_layout.addWidget(self._fatigue)
        attrs_layout.addWidget(QLabel("步数"))
        attrs_layout.addWidget(self._step)
        attrs_layout.addStretch(1)

        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(8)

        header_layout = QFormLayout()
        header_layout.setSpacing(8)
        header_layout.addRow("位置", self._location)
        header_layout.addRow("属性", attrs_row)
        root_layout.addLayout(header_layout)

        text_grid = QGridLayout()
        text_grid.setHorizontalSpacing(10)
        text_grid.setVerticalSpacing(8)
        text_grid.addWidget(QLabel("背包"), 0, 0)
        text_grid.addWidget(QLabel("计划"), 0, 1)
        text_grid.addWidget(self._inventory, 1, 0)
        text_grid.addWidget(self._plan, 1, 1)
        text_grid.addWidget(QLabel("动作"), 2, 0)
        text_grid.addWidget(QLabel("反思"), 2, 1)
        text_grid.addWidget(self._action, 3, 0)
        text_grid.addWidget(self._reflect, 3, 1)
        text_grid.addWidget(QLabel("记忆"), 4, 0, 1, 2)
        text_grid.addWidget(self._memory, 5, 0, 1, 2)
        root_layout.addLayout(text_grid)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def update_view(self, payload: Dict[str, Any]) -> None:
        # payload 由 main._build_monitor_payload 构造，字段为扁平结构。
        self.setTitle(f"智能体 | {payload.get('actor_id', self._actor_id)}")
        self._location.setText(str(payload.get("location", "-")))
        self._hunger.setText(str(payload.get("hunger", 0)))
        self._thirst.setText(str(payload.get("thirst", 0)))
        self._fatigue.setText(str(payload.get("fatigue", 0)))
        self._step.setText(str(payload.get("step", 0)))

        self._inventory.setPlainText(str(payload.get("inventory_text", "")))
        self._plan.setPlainText(str(payload.get("plan", "")))
        self._reflect.setPlainText(str(payload.get("reflect", "")))
        self._memory.setPlainText(str(payload.get("memory", "")))

        action_text = str(payload.get("action", "")).strip()
        history_entry = str(payload.get("history_entry", "")).strip()
        if history_entry:
            old_text = self._action.toPlainText().strip()
            self._action.setPlainText(f"{old_text}\n{history_entry}".strip())
            self._action.verticalScrollBar().setValue(self._action.verticalScrollBar().maximum())
        else:
            self._action.setPlainText(action_text)


class MonitorWindow(QMainWindow):
    def __init__(self, actor_ids: Iterable[str]):
        super().__init__()
        self.setWindowTitle("AITown 智能体监控面板")
        self.resize(980, 680)
        self.setMinimumSize(900, 620)

        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        self._cards: Dict[str, AgentCard] = {}
        self._ordered_ids: List[str] = list(actor_ids)
        while len(self._ordered_ids) < 4:
            self._ordered_ids.append(f"角色-{len(self._ordered_ids) + 1}")
        self._ordered_ids = self._ordered_ids[:4]

        center = QWidget()
        root = QVBoxLayout(center)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("智能体控制台")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addWidget(title)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._buttons: List[QPushButton] = []

        button_bar = QWidget()
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        self._stack = QStackedWidget()
        for idx, actor_id in enumerate(self._ordered_ids):
            btn = QPushButton(f"角色{idx + 1}：{actor_id}")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self._switch_agent(i, checked))
            self._button_group.addButton(btn, idx)
            self._buttons.append(btn)
            button_layout.addWidget(btn)

            card = AgentCard(actor_id)
            self._cards[actor_id] = card
            self._stack.addWidget(card)

        self._buttons[0].setChecked(True)
        self._stack.setCurrentIndex(0)
        root.addWidget(button_bar)
        root.addWidget(self._stack, 1)
        self.setCentralWidget(center)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain_updates)
        # 定时拉取队列，避免模拟线程直接跨线程操作 UI。
        self._timer.start(100)

        self.setStyleSheet(
            """
            QMainWindow {
                background: #f4f6f8;
            }
            QLabel#pageTitle {
                font-size: 18px;
                font-weight: 700;
                color: #1f2933;
                padding: 2px 4px;
            }
            QPushButton {
                border: 1px solid #c8d0d8;
                border-radius: 10px;
                background: #ffffff;
                color: #24323f;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #eef3f7;
            }
            QPushButton:checked {
                background: #0f7b6c;
                color: #ffffff;
                border: 1px solid #0f7b6c;
            }
            QGroupBox {
                border: 1px solid #d5dee6;
                border-radius: 12px;
                margin-top: 8px;
                background: #ffffff;
                font-weight: 700;
                color: #1f2933;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                color: #24323f;
            }
            QPlainTextEdit {
                background: #fbfcfd;
                border: 1px solid #dce4eb;
                border-radius: 8px;
                color: #1f2933;
                padding: 6px 8px;
                font-family: Consolas, 'Microsoft YaHei UI', 'Courier New', monospace;
                font-size: 12px;
            }
            """
        )

    def _switch_agent(self, index: int, checked: bool) -> None:
        if checked:
            self._stack.setCurrentIndex(index)

    def push_update(self, payload: Dict[str, Any]) -> None:
        self._queue.put(payload)

    def _drain_updates(self) -> None:
        # 每个 tick 批量消费队列，保证 UI 刷新不会阻塞仿真线程。
        while True:
            try:
                payload = self._queue.get_nowait()
            except queue.Empty:
                break
            actor_id = str(payload.get("actor_id", ""))
            card = self._cards.get(actor_id)
            if card is not None:
                card.update_view(payload)


def run_monitor(
    start_simulation: Callable[[Callable[[Dict[str, Any]], None]], None],
    actor_ids: Iterable[str],
) -> None:
    # 入口：启动 GUI，再让外部注入仿真启动函数。
    app = QApplication(sys.argv)
    win = MonitorWindow(actor_ids=actor_ids)
    win.show()
    start_simulation(win.push_update)
    app.exec_()
