#------------------------------------------------------------------------------
# Copyright (c) 2007, Riverbank Computing Limited
# All rights reserved.
#
# This software is provided without warranty under the terms of the GPL v2
# license.
#
# Author: Riverbank Computing Limited
#------------------------------------------------------------------------------

""" Creates a PyQt user interface for a specified UI object, where the UI
    is "live", meaning that it immediately updates its underlying object(s).
"""

#-------------------------------------------------------------------------------
#  Imports:
#-------------------------------------------------------------------------------

from PyQt4 import QtCore, QtGui

from helper \
    import restore_window, save_window, UnboundedScrollArea
    
from ui_base \
    import BaseDialog
    
from ui_panel \
    import panel, show_help
    
from constants \
    import DefaultTitle, WindowColor, screen_dy

from enthought.traits.ui.undo \
    import UndoHistory
    
from enthought.traits.ui.menu \
    import UndoButton, RevertButton, OKButton, CancelButton, HelpButton

#-------------------------------------------------------------------------------
#  Constants:
#-------------------------------------------------------------------------------

# Types of supported windows:
NONMODAL = 0
MODAL    = 1
POPUP    = 2

#-------------------------------------------------------------------------------
#  Creates a 'live update' PyQt user interface for a specified UI object:
#-------------------------------------------------------------------------------

def ui_live ( ui, parent ):
    """ Creates a live, non-modal PyQt user interface for a specified UI
    object.
    """
    ui_dialog( ui, parent, NONMODAL )

def ui_livemodal ( ui, parent ):
    """ Creates a live, modal PyQt user interface for a specified UI object.
    """
    ui_dialog( ui, parent, MODAL )

def ui_popup ( ui, parent ):
    """ Creates a live, modal popup PyQt user interface for a specified UI
        object.
    """
    ui_dialog( ui, parent, POPUP )

def ui_dialog ( ui, parent, style ):
    """ Creates a live PyQt user interface for a specified UI object.
    """
    if ui.owner is None:
        ui.owner = LiveWindow()

    ui.owner.init( ui, parent, style )
    ui.control = ui.owner.control
    ui.control._parent = parent

    try:
        ui.prepare_ui()
    except:
        ui.control.setParent(None)
        ui.control.ui = None
        ui.control    = None
        ui.owner      = None
        ui.result     = False
        raise

    ui.handler.position( ui.info )
    restore_window( ui )

    if style == MODAL:
        ui.control.exec_()
    else:
        ui.control.show()

#-------------------------------------------------------------------------------
#  'LiveWindow' class:
#-------------------------------------------------------------------------------
    
class LiveWindow ( BaseDialog ):
    """ User interface window that immediately updates its underlying object(s).
    """
    
    #---------------------------------------------------------------------------
    #  Initializes the object:
    #---------------------------------------------------------------------------

    def init ( self, ui, parent, style ):
        # FIXME: Note that we treat MODAL and POPUP as equivalent until we have
        # an example that demonstrates how POPUP is supposed to work.
        self.is_modal = (style != NONMODAL)
        view = ui.view
        history = ui.history
        window = ui.control

        if window is not None:
            layout = window.layout()

            if history is not None:
                history.on_trait_change( self._on_undoable, 'undoable',
                                         remove = True )
                history.on_trait_change( self._on_redoable, 'redoable',
                                         remove = True )
                history.on_trait_change( self._on_revertable, 'undoable',
                                         remove = True )
            ui.reset()
        else:
            layout = None

            self.ui = ui

            flags = QtCore.Qt.WindowSystemMenuHint
            if view.resizable:
                flags |= QtCore.Qt.WindowMinMaxButtonsHint
            else:
                flags |= QtCore.Qt.MSWindowsFixedSizeDialogHint

            window = QtGui.QDialog(parent, flags)

            window.setModal(self.is_modal)

            if view.title != '':
                window.setWindowTitle(view.title)
            else:
                window.setWindowTitle(DefaultTitle)

            window.connect(window, QtCore.SIGNAL('finished(int)'),
                self._on_finished)

            self.control = window
            self.set_icon( view.icon )

        if layout is None:
            layout = QtGui.QVBoxLayout(window)

        if not view.resizable:
            layout.setSizeConstraint(QtGui.QLayout.SetFixedSize)

        buttons = [ self.coerce_button( button ) for button in view.buttons ]
        nbuttons    = len( buttons )
        no_buttons  = ((nbuttons == 1) and self.is_button( buttons[0], '' ))
        has_buttons = ((not no_buttons) and ((nbuttons > 0) or view.undo or
                                         view.revert or view.ok or view.cancel))
        if has_buttons or (view.menubar is not None):
            if history is None:
                history = UndoHistory()
        else:
            history = None
        ui.history = history
        
        # Create the actual trait sheet panel and imbed it in a scrollable 
        # window (if requested):
        if ui.scrollable:
            sw = UnboundedScrollArea()
            sw.setFrameShape(QtGui.QFrame.NoFrame)
            layout.addWidget(sw)
            pan = panel(ui, sw)
            sw.setWidget(pan)
        else:
            pan = panel(ui, window)
            layout.addWidget(pan)

        # Remove any margin from the panel so that it lines up with the
        # buttons.
        pan.layout().setMargin(0)

        # Check to see if we need to add any of the special function buttons:
        if (not no_buttons) and (has_buttons or view.help):
            bbox = QtGui.QDialogButtonBox()
            
            # Convert all button flags to actual button actions if no buttons
            # were specified in the 'buttons' trait:
            if nbuttons == 0:
                if view.undo:
                    self.check_button( buttons, UndoButton )
                if view.revert:
                    self.check_button( buttons, RevertButton )
                if view.ok:
                    self.check_button( buttons, OKButton )
                if view.cancel:
                    self.check_button( buttons, CancelButton )
                if view.help:
                    self.check_button( buttons, HelpButton )
                
            # Create a button for each button action:
            for button in buttons:
                button = self.coerce_button(button)

                if self.is_button(button, 'Undo'):
                    self.undo = self.add_button(button, bbox,
                            QtGui.QDialogButtonBox.ActionRole, self._on_undo,
                            False)
                    history.on_trait_change(self._on_undoable, 'undoable',
                            dispatch='ui')
                    if history.can_undo:
                        self._on_undoable(True)

                    self.redo = self.add_button(button, bbox, 
                            QtGui.QDialogButtonBox.ActionRole, self._on_redo,
                            False, 'Redo')
                    history.on_trait_change(self._on_redoable, 'redoable',
                            dispatch='ui')
                    if history.can_redo:
                        self._on_redoable(True)

                elif self.is_button(button, 'Revert'): 
                    self.revert = self.add_button(button, bbox,
                            QtGui.QDialogButtonBox.ResetRole, self._on_revert,
                            False)
                    history.on_trait_change(self._on_revertable, 'undoable',
                            dispatch='ui')
                    if history.can_undo:
                        self._on_revertable(True)

                elif self.is_button(button, 'OK'): 
                    self.ok = self.add_button(button, bbox,
                            QtGui.QDialogButtonBox.AcceptRole, window.accept)
                    ui.on_trait_change(self._on_error, 'errors', dispatch='ui')

                elif self.is_button(button, 'Cancel'): 
                    self.add_button(button, bbox,
                            QtGui.QDialogButtonBox.RejectRole, window.reject)

                elif self.is_button(button, 'Help'): 
                    self.add_button(button, bbox,
                            QtGui.QDialogButtonBox.HelpRole, self._on_help)

                elif not self.is_button(button, ''):
                    self.add_button(button, bbox,
                            QtGui.QDialogButtonBox.ActionRole)

            layout.addWidget(bbox)
        
        # Add the menu bar and tool bar (if any):
        self.add_menubar()
        self.add_toolbar()

    #---------------------------------------------------------------------------
    #  Closes the dialog window:
    #---------------------------------------------------------------------------
            
    def close ( self, rc ):            
        """ Closes the dialog window.
        """
        save_window(self.ui)
        if self.is_modal:
            self.control.done(rc)
        self.ui.finish(rc)
        self.ui = self.undo = self.redo = self.revert = self.control = None

    #---------------------------------------------------------------------------
    #  Handles the user finishing with the dialog:
    #---------------------------------------------------------------------------
 
    def _on_finished ( self, result ):
        """ Handles the user finishing with the dialog.
        """
        accept = bool(result)

        if self.ui.handler.close(self.ui.info, accept):
            if not accept and self.ui.history is not None:
                self._on_revert()

            self.close(accept)

    #---------------------------------------------------------------------------
    #  Handles an 'Undo' change request:
    #---------------------------------------------------------------------------
           
    def _on_undo ( self ):
        """ Handles an "Undo" change request.
        """
        self.ui.history.undo()
   
    #---------------------------------------------------------------------------
    #  Handles a 'Redo' change request:
    #---------------------------------------------------------------------------
           
    def _on_redo ( self ):
        """ Handles a "Redo" change request.
        """
        self.ui.history.redo()
   
    #---------------------------------------------------------------------------
    #  Handles a 'Revert' all changes request:
    #---------------------------------------------------------------------------
           
    def _on_revert ( self ):
        """ Handles a request to revert all changes.
        """
        ui = self.ui
        ui.history.revert()
        ui.handler.revert( ui.info )
   
    #---------------------------------------------------------------------------
    #  Handles editing errors:
    #---------------------------------------------------------------------------
                        
    def _on_error ( self, errors ):
        """ Handles editing errors.
        """
        self.ok.setEnabled(errors == 0)
    
    #---------------------------------------------------------------------------
    #  Handles the 'Help' button being clicked:
    #---------------------------------------------------------------------------
           
    def _on_help ( self, event ):
        """ Handles the 'user clicking the Help button.
        """
        self.ui.handler.show_help( self.ui.info, event.GetEventObject() )
            
    #---------------------------------------------------------------------------
    #  Handles the undo history 'undoable' state changing:
    #---------------------------------------------------------------------------
            
    def _on_undoable ( self, state ):
        """ Handles a change to the "undoable" state of the undo history 
        """
        self.undo.setEnabled(state)
            
    #---------------------------------------------------------------------------
    #  Handles the undo history 'redoable' state changing:
    #---------------------------------------------------------------------------
            
    def _on_redoable ( self, state ):
        """ Handles a change to the "redoable state of the undo history.
        """
        self.redo.setEnabled(state)
            
    #---------------------------------------------------------------------------
    #  Handles the 'revert' state changing:
    #---------------------------------------------------------------------------
            
    def _on_revertable ( self, state ):
        """ Handles a change to the "revert" state.
        """
        self.revert.setEnabled(state)