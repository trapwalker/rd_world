# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_world.registry.quests.agent_event_quests import AgentEventQuest
from sublayers_world.registry.quests.ai_event_quests.traffic.gang.caravan_simple import AICaravanQuest
from sublayers_server.model.quest_events import OnCancel, OnTimer

from functools import partial


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

    def get_current_caravan_position(self, event_quest):
        # todo: взять средневзвешенную точку каравана, а пока взята текущая точка маршрута
        return event_quest.dc.route.get_current_point()

    def calc_participation(self, car_pos, caravan_pos):
        if car_pos.distance(caravan_pos) <= 3000:
            self.dc.count_participation += 1.0

    ####################################################################################################################
    def on_start_(self, event, **kw):
        self.dc.check_participation = 0.0
        self.dc.count_participation = 0.0
        self.dc.caravan_started = False

    ####################################################################################################################
    class begin(AgentEventQuest.begin):
        def on_enter_(self, quest, event):
            super(EscortCaravan.begin, self).on_enter_(quest=quest, event=event)
            quest.set_timer(event=event, name='participation', delay=30)
            quest.log(u'Ожидание каравана.', event=event)

        def on_event_(self, quest, event):
            super(EscortCaravan.begin, self).on_event_(quest=quest, event=event)
            if isinstance(event, OnTimer) and event.name == 'participation':
                quest.set_timer(event=event, name='participation', delay=30)
                event_quest = quest.get_event_quest(event=event)
                if event_quest.current_state == 'run':  # Если караван в пути
                    if not quest.dc.caravan_started:
                        quest.dc.caravan_started = True
                        quest.log(u'Караван выехал.', event=event)
                    caravan_point = quest.get_current_caravan_position(event_quest=event_quest)
                    if caravan_point:
                        quest.dc.check_participation += 1.0
                        if quest.agent.profile._agent_model and quest.agent.profile._agent_model.car:
                            quest.calc_participation(car_pos=quest.agent.profile._agent_model.car.position(event.time), caravan_pos=caravan_point)


    class win(AgentEventQuest.win):
        def on_enter_(self, quest, event):
            if quest.dc.check_participation == 0:
                quest.dc.check_participation = 1.0
            p = int(100 * quest.dc.count_participation / quest.dc.check_participation)
            quest.log(u'Участие в караване: {}'.format(p), event=event)
            super(EscortCaravan.win, self).on_enter_(quest=quest, event=event)