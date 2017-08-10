# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_world.registry.quests.agent_event_quests import AgentEventQuest
from sublayers_world.registry.quests.ai_event_quests.traffic.gang.caravan_simple import AICaravanQuest


class EscortCaravan(AgentEventQuest):
    def get_potential_event_quest(self, event, agent):
        event_quests = event.server.ai_dispatcher.get_quest_by_tags(set(self.needed_tags))
        npc_view_quests = agent.profile.npc_view_quests
        for event_quest in event_quests:
            flag = False
            for agent_quest in npc_view_quests:
                if isinstance(agent_quest, AgentEventQuest) and (
                                agent_quest.event_quest_uid == str(event_quest.uid) or  # Если квест на такой караван уже есть у агента
                                event_quest.dc.start_caravan_time <= event.time):  # или Если караван уже уехал
                    flag = True
                    break
            if not flag:
                return event_quest
        log.debug('EscortCaravan :: get_potential_event_quest :: None')
        return None

    def can_generate(self, event):
        if not super(EscortCaravan, self).can_generate(event=event):
            return False
        event_quest = self.get_event_quest(event=event)

        if event_quest and isinstance(event_quest, AICaravanQuest) and event.time < event_quest.dc.start_caravan_time:
            self.shelf_life_time = event_quest.dc.start_caravan_time - event.time
            log.debug('shelf_life_time is %s', self.shelf_life_time)
        else:
            return False
        return True


    def on_generate_(self, event, **kw):
        super(EscortCaravan, self).on_generate_(event=event, **kw)

