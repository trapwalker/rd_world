# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_world.registry.quests.ai_event_quests.traffic.gang import AIGangQuest


class AIMultiGangQuest(AIGangQuest):
    def on_see_object(self, event):  # Вызывается когда только для OnAISee
        obj = getattr(event, 'obj', None)
        if obj is None:
            return
        main_agent = getattr(obj, 'main_agent', None)
        if not main_agent:
            return
        if not self.is_observer(obj):
            return
        event_quest = getattr(main_agent, 'event_quest', None)

        if event_quest and event_quest.generation_group == self.dc.members[0].event_quest.generation_group:
            return

        # Добавить во враги
        obj_uid = obj.uid

        if obj_uid in [agent.car.uid for agent in self.dc.members if agent.car and not agent.car.limbo]:
            return

        if obj_uid not in self.dc.target_uid_list:
            self.dc.target_uid_list.append(obj_uid)

