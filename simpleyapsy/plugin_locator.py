import os
import re
import logging
from configparser import ConfigParser

from simpleyapsy import PluginInfo
from simpleyapsy import PLUGIN_NAME_FORBIDEN_STRING
from simpleyapsy import log
from simpleyapsy.file_getters import WithInfoFileExt 

class PluginLocator(object):
    """
    Locates plugins on the file system using a set of analyzers to
    determine what files actually corresponds to plugins.
    
    If more than one analyzer is being used, the first that will discover a
    new plugin will avoid other strategies to find it too.

    By default each directory set as a "plugin place" is scanned
    recursively. You can change that by a call to
    ``disableRecursiveScan``.
    """
    
    def __init__(self, 
                 file_getters=[WithInfoFileExt('yapsy-plugin')],
                 directory_list=[],
                 recursive=True):

        if directory_list == []:
            directory_list = [os.path.dirname(__file__)]

        self.directory_list = directory_list
        self.file_getters = file_getters
        self.recursive = recursive 
        self._discovered_plugins = {}
        self._plugin_info_cls_map = {}
        self._max_size = 1e3*1024 # in octets (by default 1 Mo)
            
    def remove_analyzer_by_param(self, class_name=None, instance_attr=None):
        # FIXME !!
        """
        Removes analyzers of a given name.
        """
        foundAndRemoved = False
        for analyzer in enumerate(self.analyzers):
            if obj.name == name:
                self.analyzers.remove(obj)
                foundAndRemoved = True

    def _getInfoForPluginFromAnalyzer(self,analyzer,dirpath, filename):
        """
        Return an instance of plugin_info_cls filled with data extracted by the analyzer.

        May return None if the analyzer fails to extract any info.
        """
        plugin_info_dict,config_parser = analyzer.getInfosDictFromPlugin(dirpath, filename)
        if plugin_info_dict is None:
            return None
        plugin_info_cls = self._plugin_info_cls_map.get(analyzer, self._default_plugin_info_cls)
        plugin_info = plugin_info_cls(plugin_info_dict["name"],plugin_info_dict["path"])
        plugin_info.details = config_parser
        return plugin_info
    
    def locatePlugins(self):
        """
        Walk through the plugins' places and look for plugins.

        Return the candidates and number of plugins found.
        """
        _candidates = []
        _discovered = {}
        for directory in map(os.path.abspath, self.plugins_places):
            # first of all, is it a directory :)
            if not os.path.isdir(directory):
                log.debug("%s skips %s (not a directory)" % (self.__class__.__name__, directory))
                if self.recursive:
                    debug_txt_mode = "recursively"
                    walk_iter = os.walk(directory, followlinks=True)
                else:
                    debug_txt_mode = "non-recursively"
                    walk_iter = [(directory,[],os.listdir(directory))]
                # iteratively walks through the directory
                log.debug("%s walks (%s) into directory: %s" % (self.__class__.__name__, debug_txt_mode, directory))
                for item in walk_iter:
                    dirpath = item[0]
                    for filename in item[2]:
                            # print("testing candidate file %s" % filename)
                            for analyzer in self._analyzers:
                                    # print("... with analyzer %s" % analyzer.name)
                                    # eliminate the obvious non plugin files
                                    if not analyzer.isValidPlugin(filename):
                                            log.debug("%s is not a valid plugin for strategy %s" % (filename, analyzer))
                                            continue
                                    candidate_infofile = os.path.join(dirpath, filename)
                                    if candidate_infofile in _discovered:
                                            log.debug("%s (with strategy %s) rejected because already discovered" % (candidate_infofile, analyzer))
                                            continue
                                    log.debug("%s found a candidate:\n    %s" % (self.__class__.__name__, candidate_infofile))
#						print candidate_infofile
                                    plugin_info = self._getInfoForPluginFromAnalyzer(analyzer, dirpath, filename)
                                    if plugin_info is None:
                                            log.warning("Plugin candidate '%s'  rejected by strategy '%s'" % (candidate_infofile, analyzer))
                                            break # we consider this was the good strategy to use for: it failed -> not a plugin -> don't try another strategy
                                    # now determine the path of the file to execute,
                                    # depending on wether the path indicated is a
                                    # directory or a file
#					print plugin_info.path
                                    # Remember all the files belonging to a discovered
                                    # plugin, so that strategies (if several in use) won't
                                    # collide
                                    if os.path.isdir(plugin_info.path):
                                            candidate_filepath = os.path.join(plugin_info.path, "__init__")
                                            # it is a package, adds all the files concerned
                                            for _file in os.listdir(plugin_info.path):
                                                    if _file.endswith(".py"):
                                                            self._discovered_plugins[os.path.join(plugin_info.path, _file)] = candidate_filepath
                                                            _discovered[os.path.join(plugin_info.path, _file)] = candidate_filepath
                                    elif (plugin_info.path.endswith(".py") and os.path.isfile(plugin_info.path)) or os.path.isfile(plugin_info.path+".py"):
                                            candidate_filepath = plugin_info.path
                                            if candidate_filepath.endswith(".py"):
                                                    candidate_filepath = candidate_filepath[:-3]
                                            # it is a file, adds it
                                            self._discovered_plugins[".".join((plugin_info.path, "py"))] = candidate_filepath
                                            _discovered[".".join((plugin_info.path, "py"))] = candidate_filepath
                                    else:
                                            log.error("Plugin candidate rejected: cannot find the file or directory module for '%s'" % (candidate_infofile))
                                            break
#					print candidate_filepath
                                    _candidates.append((candidate_infofile, candidate_filepath, plugin_info))
                                    # finally the candidate_infofile must not be discovered again
                                    _discovered[candidate_infofile] = candidate_filepath
                                    self._discovered_plugins[candidate_infofile] = candidate_filepath
#						print "%s found by strategy %s" % (candidate_filepath, analyzer.name)
        return _candidates, len(_candidates)

    def gatherCorePluginInfo(self, directory, filename):
        """
        Return a ``PluginInfo`` as well as the ``ConfigParser`` used to build it.
        
        If filename is a valid plugin discovered by any of the known
        strategy in use. Returns None,None otherwise.
        """
        for analyzer in self._analyzers:
            # eliminate the obvious non plugin files
            if not analyzer.isValidPlugin(filename):
                continue
            plugin_info = self._getInfoForPluginFromAnalyzer(analyzer,directory, filename)
            return plugin_info,plugin_info.details
        return None,None
    
    def setPluginInfoClass(self, picls, name=None):
        """
        Set the class that holds PluginInfo. The class should inherit
        from ``PluginInfo``.

        If name is given, then the class will be used only by the corresponding analyzer.
        
        If name is None, the class will be set for all analyzers.
        """
        if name is None:
            self._default_plugin_info_cls = picls
            self._plugin_info_cls_map = {}
        else:
            self._plugin_info_cls_map[name] = picls
