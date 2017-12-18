# -*- coding: utf-8 -*-

from sublayers_server.model.registry_me.classes.quests import Quest
from sublayers_server.model.registry_me.tree import RegistryLinkField


class ClassTypeQuest(Quest):
    next_quest = RegistryLinkField(
        caption=u"Прототип следующего классового квеста",
        document_type='sublayers_server.model.registry_me.classes.quests.Quest',
    )


