# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import FloatField, LocalizedString
from sublayers_server.model.utils import getKarmaNameLocalizedString

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestKarmaLimit(ClassTypeQuest):
    needed_karma = FloatField(caption=u"Минимальное значение кармы", tags={'client'})

    def init_text(self):
        self.text = LocalizedString(_id="q_cq_karmic_journal_text").generate(
            name_needed=self.locale(getKarmaNameLocalizedString(self.needed_karma)),
        )  ##LOCALIZATION

    def on_start_(self, event, **kw):
        self.init_text()
        self.log(text=self.locale("q_cq_karmic_started"), event=event)  ##LOCALIZATION


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.KarmaLimitQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_karmic_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_karmic_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.agent.profile.karma_norm >= quest.needed_karma:
                    quest.agent.profile.del_note(uid=quest.dc.quest_note, time=event.time)
                    quest.go(event=event, new_state="win")
                else:
                    text = LocalizedString(_id="q_cq_karmic_replica_not_finish").generate(  ##LOCALIZATION
                        name_needed=quest.locale(getKarmaNameLocalizedString(quest.needed_karma)),
                        name_karma_agent=quest.locale(getKarmaNameLocalizedString(quest.agent.profile.karma_norm)))
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=text,
                        event=event
                    )


    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.npc_replica(
                npc=quest.hirer,
                replica=quest.locale("q_cq_karmic_phrase_success"),  ##LOCALIZATION
                event=event
            )
            quest.log(text=quest.locale("q_cq_karmic_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
